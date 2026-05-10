import argparse
import sys
import os
import glob
import json
from src.parser import convert_to_markdown, split_pdf
from src.chunker import chunk_markdown
from src.embedder import embed_chunks
from src.searcher import search, index_all_chunks
from src.answerer import generate_answer
from src.logger import logger
from src.state import StateTracker, calculate_file_hash, calculate_dict_hash

def positive_int(value):
    int_value = int(value)
    if int_value <= 0:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return int_value

def heading_level(value):
    int_value = positive_int(value)
    if int_value > 6:
        raise argparse.ArgumentTypeError("Heading level must be between 1 and 6.")
    return int_value

def parse_cmd(args):
    if os.path.isdir(args.file):
        patterns = ["*.pdf", "*.pptx", "*.md", "*.adoc"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(args.file, p)))
            
        if not files:
            logger.info(f"No supported files found in directory: {args.file}")
            return
            
        logger.info(f"Found {len(files)} files to parse in directory: {args.file}")
        for f in files:
            try:
                convert_to_markdown(f)
            except Exception as e:
                logger.error(f"Error parsing {f}: {e}")
    else:
        try:
            convert_to_markdown(args.file)
        except Exception as e:
            logger.error(f"Error parsing {args.file}: {e}")

def chunk_cmd(args):
    chunk_level = 2
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                chunk_level = config.get("chunk_level", 2)
        except Exception:
            pass
    if args.level:
        chunk_level = args.level

    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.md"))
        if not files:
            logger.info(f"No .md files found in directory: {args.file}")
            return
            
        logger.info(f"Found {len(files)} markdown files to chunk in directory: {args.file}")
        for f in files:
            try:
                chunk_markdown(f, chunk_level=chunk_level)
            except Exception as e:
                logger.error(f"Error chunking {f}: {e}")
    else:
        try:
            chunk_markdown(args.file, chunk_level=chunk_level)
        except Exception as e:
            logger.error(f"Error chunking {args.file}: {e}")

def embed_cmd(args):
    files_embedded = False

    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.json"))
        if not files:
            logger.info(f"No .json files found in directory: {args.file}")
            return
            
        logger.info(f"Found {len(files)} JSON files to embed in directory: {args.file}")
        for f in files:
            try:
                if embed_chunks(f, force=args.force):
                    files_embedded = True
            except Exception as e:
                logger.error(f"Error embedding {f}: {e}")
    else:
        try:
            if embed_chunks(args.file, force=args.force):
                files_embedded = True
        except Exception as e:
            logger.error(f"Error embedding {args.file}: {e}")

    if files_embedded:
        logger.info("Rebuilding search index after embedding updates...")
        index_all_chunks()

def sync_cmd(args):
    tracker = StateTracker()

    config_path = "config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    # 1. Handle Configuration Changes
    current_config_hash = calculate_dict_hash(config)
    if tracker.get_config_hash() != current_config_hash:
        if tracker.get_config_hash() != "":
            logger.info("Configuration changed (hash updated).")
        tracker.set_config_hash(current_config_hash)

    # Force full re-process if --rebuild is specified
    if args.rebuild:
        logger.warning("Forcing full re-process as requested by --rebuild.")
        tracker.clear_state()

    input_dir = "input"
    if not os.path.exists(input_dir):
        logger.error(f"Input directory '{input_dir}' does not exist.")
        return

    patterns = ["*.pdf", "*.pptx", "*.md", "*.adoc"]
    current_input_files = []
    for p in patterns:
        current_input_files.extend(glob.glob(os.path.join(input_dir, p)))
    current_input_files = [os.path.normpath(f) for f in current_input_files]

    # 2. Handle Deletions
    tracked_files = tracker.get_all_tracked_files()
    for tracked_file in tracked_files:
        if tracked_file not in current_input_files:
            logger.info(f"File deleted: {tracked_file}. Cleaning up generated files...")
            record = tracker.get_file_record(tracked_file)
            parsed_file = record.get("parsed_file")
            chunk_file = record.get("chunk_file")
            
            if parsed_file and os.path.exists(parsed_file):
                os.remove(parsed_file)
            if chunk_file and os.path.exists(chunk_file):
                os.remove(chunk_file)
                
            tracker.remove_file_record(tracked_file)

    # 3. Process New or Modified Files
    chunk_level = config.get("chunk_level", 2)
    files_processed = False

    for input_file in current_input_files:
        current_hash = calculate_file_hash(input_file)
        record = tracker.get_file_record(input_file)
        
        parsed_file = record.get("parsed_file")
        chunk_file = record.get("chunk_file")
        
        is_unchanged = (record.get("hash") == current_hash)
        outputs_exist = (parsed_file and os.path.exists(parsed_file)) and \
                        (chunk_file and os.path.exists(chunk_file))
                        
        if is_unchanged and outputs_exist and record.get("status") == "embedded":
            logger.info(f"Skipping unchanged file: {input_file}")
            continue

        # Auto-split large PDFs if they exceed the split size
        if input_file.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(input_file)
                total_pages = len(reader.pages)
                
                pages_per_file = config.get("pdf_split_pages", 20)
                
                if total_pages > pages_per_file:
                    logger.warning(f"{input_file} has {total_pages} pages, exceeding split size of {pages_per_file}. Auto-splitting...")
                    from src.parser import split_pdf
                    new_parts = split_pdf(input_file, pages_per_file=pages_per_file)
                    # Add new parts to the list to be processed in the current loop
                    current_input_files.extend([os.path.normpath(p) for p in new_parts])
                    logger.info(f"Auto-split completed. Added {len(new_parts)} parts to processing queue. Skipping original file.")
                    continue
            except Exception as e:
                logger.error(f"Error checking page count or splitting {input_file}: {e}")

        logger.info(f"Processing new or modified file: {input_file}")
        files_processed = True
        try:
            parsed_path = convert_to_markdown(input_file)
            if not parsed_path:
                continue

            chunk_path = chunk_markdown(parsed_path, chunk_level=chunk_level)

            embedded = False
            if chunk_path:
                embedded = embed_chunks(chunk_path)

            tracker.update_file_record(input_file, {
                "hash": current_hash,
                "parsed_file": parsed_path,
                "chunk_file": chunk_path,
                "status": "embedded" if embedded else "chunked"
            })
        except Exception as e:
            logger.error(f"Error processing {input_file}: {e}")

    # 4. Rebuild Search Index
    if files_processed or len(tracked_files) != len(current_input_files):
        logger.info("Rebuilding search index (Whoosh & Qdrant) to reflect changes...")
        index_all_chunks()
    else:
        logger.info("No files were changed. Index rebuild skipped.")

    logger.info("Sync completed.")

def search_cmd(args):
    try:
        search(args.query)
    except Exception as e:
        logger.error(f"Error during search: {e}")

def config_cmd(args):
    config_path = "config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
    updated = False
    if args.max_size is not None:
        config["log_max_bytes"] = args.max_size
        updated = True
    if args.backup_count is not None:
        config["log_backup_count"] = args.backup_count
        updated = True
    if args.ocr is not None:
        config["do_ocr"] = (args.ocr == 'true')
        updated = True
    if args.split_pages is not None:
        config["pdf_split_pages"] = args.split_pages
        updated = True
    if args.chunk_level is not None:
        config["chunk_level"] = args.chunk_level
        updated = True
    if args.llm_model is not None:
        config["llm_model"] = args.llm_model
        updated = True
    if args.llm_temperature is not None:
        config["llm_temperature"] = args.llm_temperature
        updated = True
    if args.llm_system_prompt is not None:
        config["llm_system_prompt"] = args.llm_system_prompt
        updated = True
    if args.llm_user_prompt is not None:
        config["llm_user_prompt_template"] = args.llm_user_prompt
        updated = True
    if args.search_limit is not None:
        config["search_limit"] = args.search_limit
        updated = True
    if args.embed_workers is not None:
        config["embed_workers"] = args.embed_workers
        updated = True
        
    if updated:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Updated config: {config}")
        logger.info("Changes will take effect on the next run.")
    else:
        logger.info(f"Current config: {config}")

def split_cmd(args):
    config_path = "config.json"
    pages_per_file = 20
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                pages_per_file = config.get("pdf_split_pages", pages_per_file)
        except Exception:
            pass
            
    if args.pages is not None:
        pages_per_file = args.pages
        
    try:
        split_pdf(args.file, pages_per_file=pages_per_file)
    except Exception as e:
        logger.error(f"Error splitting PDF {args.file}: {e}")

def ask_cmd(args):
    try:
        hit_ids = search(args.query)
        
        if not hit_ids:
            print("\n該当する情報が見つかりませんでした。")
            return
            
        print("\n回答を生成中...")
        answer = generate_answer(args.query, hit_ids)
        
        print("\n=== 回答 ===")
        print(answer)
        print("============")
        
    except Exception as e:
        logger.error(f"Error during ask command: {e}")

def main():
    parser = argparse.ArgumentParser(description="RAG PoC CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync cmd
    sync_parser = subparsers.add_parser("sync", help="Automatically process new/modified/deleted files in input/")
    sync_parser.add_argument("--rebuild", action="store_true", help="Force full re-process of all files")

    # parse cmd
    parse_parser = subparsers.add_parser("parse", help="Convert PDF/PPTX to Markdown (Supports file or directory)")
    parse_parser.add_argument("file", help="Path to input file or directory")

    # chunk cmd
    chunk_parser = subparsers.add_parser("chunk", help="Chunk Markdown by heading (Supports file or directory)")
    chunk_parser.add_argument("file", help="Path to markdown file or directory")
    chunk_parser.add_argument("--level", type=int, help="Heading level to chunk at (overrides config.json)")

    # embed cmd
    embed_parser = subparsers.add_parser("embed", help="Embed chunks (Supports file or directory)")
    embed_parser.add_argument("file", help="Path to chunk JSON file or directory")
    embed_parser.add_argument("--force", action="store_true", help="Force re-embedding of all chunks")

    # search cmd
    search_parser = subparsers.add_parser("search", help="Execute search")
    search_parser.add_argument("query", help="Search query string")

    # config cmd
    config_parser = subparsers.add_parser("config", help="Get/Set configuration")
    config_parser.add_argument("--max-size", type=positive_int, help="Max log file size in bytes")
    config_parser.add_argument("--backup-count", type=positive_int, help="Backup file count")
    config_parser.add_argument("--ocr", choices=['true', 'false'], help="Enable/Disable OCR (true/false)")
    config_parser.add_argument("--split-pages", type=positive_int, help="Pages per split PDF file")
    config_parser.add_argument("--chunk-level", type=heading_level, help="Heading level to chunk at")
    config_parser.add_argument("--llm-model", help="OpenAI model for answer generation")
    config_parser.add_argument("--llm-temperature", type=float, help="Temperature for answer generation")
    config_parser.add_argument("--llm-system-prompt", help="System prompt for answer generation")
    config_parser.add_argument("--llm-user-prompt", help="User prompt template for answer generation")
    config_parser.add_argument("--search-limit", type=positive_int, help="Number of chunks to retrieve for search")
    config_parser.add_argument("--embed-workers", type=positive_int, help="Number of parallel workers for embedding")

    # split cmd
    split_parser = subparsers.add_parser("split", help="Split PDF into smaller files")
    split_parser.add_argument("file", help="Path to PDF file")
    split_parser.add_argument("--pages", type=positive_int, help="Pages per split file (overrides config)")

    # ask cmd
    ask_parser = subparsers.add_parser("ask", help="Search and generate answer using LLM (RAG)")
    ask_parser.add_argument("query", help="Question string")

    args = parser.parse_args()

    if args.command == "sync":
        sync_cmd(args)
    elif args.command == "parse":
        parse_cmd(args)
    elif args.command == "chunk":
        chunk_cmd(args)
    elif args.command == "embed":
        embed_cmd(args)
    elif args.command == "search":
        search_cmd(args)
    elif args.command == "config":
        config_cmd(args)
    elif args.command == "split":
        split_cmd(args)
    elif args.command == "ask":
        ask_cmd(args)

if __name__ == "__main__":
    main()
