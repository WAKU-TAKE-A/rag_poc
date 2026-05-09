import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def embed_chunks(chunks_path: str):
    print(f"Embedding chunks in {chunks_path}...")
    
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set it in a .env file or your environment.")
        return
        
    client = OpenAI()
    
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    print(f"Processing {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        print(f"Embedding chunk {i+1}/{len(chunks)}...")
        try:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            chunk["embedding"] = response.data[0].embedding
        except Exception as e:
            print(f"Error embedding chunk {i+1}: {e}")
            return
        
    # Save the chunks with embeddings
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully added embeddings to {len(chunks)} chunks in {chunks_path}")
