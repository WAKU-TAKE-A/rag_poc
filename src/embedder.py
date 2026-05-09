import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.logger import logger

load_dotenv()

def embed_chunks(chunks_path: str) -> bool:
    logger.info(f"Embedding chunks in {chunks_path}...")
    
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set.")
        logger.info("Please set it in a .env file or your environment.")
        return False
        
    client = OpenAI()
    
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    logger.info(f"Processing {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        logger.info(f"Embedding chunk {i+1}/{len(chunks)}...")
        try:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            chunk["embedding"] = response.data[0].embedding
        except Exception as e:
            logger.error(f"Error embedding chunk {i+1}: {e}")
            return False
        
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Successfully added embeddings to {len(chunks)} chunks in {chunks_path}")
    return True
