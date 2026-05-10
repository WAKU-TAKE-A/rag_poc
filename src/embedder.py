import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.logger import logger
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

def embed_chunks(chunks_path: str, force: bool = False) -> bool:
    logger.info(f"Embedding chunks in {chunks_path} (force={force})...")
    
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set.")
        logger.info("Please set it in a .env file or your environment.")
        return False
        
    # Load config for embed_workers
    embed_workers = 5
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                embed_workers = config.get("embed_workers", embed_workers)
        except Exception as e:
            logger.error(f"Error loading config for embed_workers: {e}")
            
    logger.info(f"Embed workers set to: {embed_workers}")
        
    client = OpenAI()
    
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    logger.info(f"Processing {len(chunks)} chunks...")
    
    def process_chunk(i, chunk):
        # Skip if already embedded (unless forced)
        if "embedding" in chunk and not force:
            logger.info(f"Chunk {i+1}/{len(chunks)} は既に埋め込み済みです。スキップします。")
            return True
            
        text = chunk["text"]
        logger.info(f"Embedding chunk {i+1}/{len(chunks)}...")
        try:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            chunk["embedding"] = response.data[0].embedding
            return True
        except Exception as e:
            logger.error(f"Error embedding chunk {i+1}: {e}")
            return False

    # Run embedding in parallel
    with ThreadPoolExecutor(max_workers=embed_workers) as executor:
        futures = [executor.submit(process_chunk, i, chunk) for i, chunk in enumerate(chunks)]
        results = [f.result() for f in futures]
        
    if not all(results):
        logger.error("Some chunks failed to embed.")
        return False
        
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Successfully added embeddings to {len(chunks)} chunks in {chunks_path}")
    return True
