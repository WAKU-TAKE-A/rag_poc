import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.logger import logger
from src.config import load_config, project_path
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

def embed_chunks(chunks_path: str, force: bool = False) -> bool:
    abs_chunks_path = project_path(chunks_path) if not os.path.isabs(chunks_path) else chunks_path
    logger.info(f"Embedding chunks in {abs_chunks_path} (force={force})...")

    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set.")
        logger.info("Please set it in a .env file or your environment.")
        return False

    config = load_config()
    embed_workers = config.get("embed_workers", 5)

    logger.info(f"Embed workers set to: {embed_workers}")

    client = OpenAI()

    with open(abs_chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    logger.info(f"Processing {len(chunks)} chunks...")

    def process_chunk(i, text, has_embedding):
        # Skip if already embedded (unless forced)
        if has_embedding and not force:
            logger.info(f"Chunk {i+1}/{len(chunks)} は既に埋め込み済みです。スキップします。")
            return i, None, True

        logger.info(f"Embedding chunk {i+1}/{len(chunks)}...")
        try:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return i, response.data[0].embedding, True
        except Exception as e:
            logger.error(f"Error embedding chunk {i+1}: {e}")
            return i, None, False

    # Run embedding in parallel
    with ThreadPoolExecutor(max_workers=embed_workers) as executor:
        futures = [
            executor.submit(process_chunk, i, chunk["text"], "embedding" in chunk)
            for i, chunk in enumerate(chunks)
        ]
        results = [f.result() for f in futures]

    all_success = True
    for i, embedding, success in results:
        if not success:
            all_success = False
            continue
        if embedding is not None:
            chunks[i]["embedding"] = embedding

    if not all_success:
        logger.error("Some chunks failed to embed.")
        return False

    with open(abs_chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Successfully added embeddings to {len(chunks)} chunks in {abs_chunks_path}")
    return True
