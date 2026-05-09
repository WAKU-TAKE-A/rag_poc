import argparse
import sys
import os
import glob
import json
from src.parser import convert_to_markdown, split_pdf
from src.chunker import chunk_markdown
from src.embedder import embed_chunks
from src.searcher import search
from src.answerer import generate_answer
from src.logger import logger

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
    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.md"))
        if not files:
            logger.info(f"No .md files found in directory: {args.file}")
            return
            
        logger.info(f"Found {len(files)} markdown files to chunk in directory: {args.file}")
        for f in files:
            try:
                chunk_markdown(f, chunk_level=args.level)
            except Exception as e:
                logger.error(f"Error chunking {f}: {e}")
    else:
        try:
            chunk_markdown(args.file, chunk_level=args.level)
        except Exception as e:
            logger.error(f"Error chunking {args.file}: {e}")

def embed_cmd(args):
    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.json"))
        if not files:
            logger.info(f"No .json files found in directory: {args.file}")
            return
            
        logger.info(f"Found {len(files)} JSON files to embed in directory: {args.file}")
        for f in files:
            try:
                embed_chunks(f)
            except Exception as e:
                logger.error(f"Error embedding {f}: {e}")
    else:
        try:
            embed_chunks(args.file)
        except Exception as e:
            logger.error(f"Error embedding {args.file}: {e}")

def search_cmd(args):
    try:
        search(args.query)
    except Exception as e:
        logger.error(f"Error during search: {e}")

def config_cmd(args):
    config_path = "config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
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
        
    if updated:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Updated config: {config}")
        logger.info("Changes will take effect on the next run.")
    else:
        logger.info(f"Current config: {config}")

def split_cmd(args):
    config_path = "config.json"
    pages_per_file = 20
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
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
        # 1. Search
        hit_ids = search(args.query)
        
        if not hit_ids:
            print("\n該当する情報が見つかりませんでした。")
            return
            
        # 2. Generate Answer
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

    # parse cmd
    parse_parser = subparsers.add_parser("parse", help="Convert PDF/PPTX to Markdown (Supports file or directory)")
    parse_parser.add_argument("file", help="Path to input file or directory")

    # chunk cmd
    chunk_parser = subparsers.add_parser("chunk", help="Chunk Markdown by heading (Supports file or directory)")
    chunk_parser.add_argument("file", help="Path to markdown file or directory")
    chunk_parser.add_argument("--level", type=int, default=2, help="Heading level to chunk at")

    # embed cmd
    embed_parser = subparsers.add_parser("embed", help="Embed chunks (Supports file or directory)")
    embed_parser.add_argument("file", help="Path to chunk JSON file or directory")

    # search cmd
    search_parser = subparsers.add_parser("search", help="Execute search")
    search_parser.add_argument("query", help="Search query string")

    # config cmd
    config_parser = subparsers.add_parser("config", help="Get/Set configuration")
    config_parser.add_argument("--max-size", type=int, help="Max log file size in bytes")
    config_parser.add_argument("--backup-count", type=int, help="Backup file count")
    config_parser.add_argument("--ocr", choices=['true', 'false'], help="Enable/Disable OCR (true/false)")
    config_parser.add_argument("--split-pages", type=int, help="Pages per split PDF file")

    # split cmd
    split_parser = subparsers.add_parser("split", help="Split PDF into smaller files")
    split_parser.add_argument("file", help="Path to PDF file")
    split_parser.add_argument("--pages", type=int, help="Pages per split file (overrides config)")

    # ask cmd
    ask_parser = subparsers.add_parser("ask", help="Search and generate answer using LLM (RAG)")
    ask_parser.add_argument("query", help="Question string")

    args = parser.parse_args()

    if args.command == "parse":
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
