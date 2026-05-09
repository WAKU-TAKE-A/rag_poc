import argparse
import sys
import os
import glob
from src.parser import convert_to_markdown
from src.chunker import chunk_markdown
from src.embedder import embed_chunks
from src.searcher import search

def parse_cmd(args):
    if os.path.isdir(args.file):
        # PDF, PPTX, MD, ADOC
        patterns = ["*.pdf", "*.pptx", "*.md", "*.adoc"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(args.file, p)))
            
        if not files:
            print(f"No supported files found in directory: {args.file}")
            return
            
        print(f"Found {len(files)} files to parse in directory: {args.file}")
        for f in files:
            try:
                convert_to_markdown(f)
            except Exception as e:
                print(f"Error parsing {f}: {e}")
    else:
        convert_to_markdown(args.file)

def chunk_cmd(args):
    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.md"))
        if not files:
            print(f"No .md files found in directory: {args.file}")
            return
            
        print(f"Found {len(files)} markdown files to chunk in directory: {args.file}")
        for f in files:
            try:
                chunk_markdown(f, chunk_level=args.level)
            except Exception as e:
                print(f"Error chunking {f}: {e}")
    else:
        chunk_markdown(args.file, chunk_level=args.level)

def embed_cmd(args):
    if os.path.isdir(args.file):
        files = glob.glob(os.path.join(args.file, "*.json"))
        if not files:
            print(f"No .json files found in directory: {args.file}")
            return
            
        print(f"Found {len(files)} JSON files to embed in directory: {args.file}")
        for f in files:
            try:
                embed_chunks(f)
            except Exception as e:
                print(f"Error embedding {f}: {e}")
    else:
        embed_chunks(args.file)

def search_cmd(args):
    search(args.query)

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

    args = parser.parse_args()

    try:
        if args.command == "parse":
            parse_cmd(args)
        elif args.command == "chunk":
            chunk_cmd(args)
        elif args.command == "embed":
            embed_cmd(args)
        elif args.command == "search":
            search_cmd(args)
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
