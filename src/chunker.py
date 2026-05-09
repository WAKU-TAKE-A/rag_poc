import json
import os
import re
from src.models import ChunkMetadata

def chunk_markdown(md_path: str, output_dir: str = "chunks", chunk_level: int = 2) -> str:
    print(f"Chunking {md_path} at heading level {chunk_level}...")
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    chunks = []
    current_heading = "Document Start"
    current_path = []
    current_text = []
    chunk_counter = 1
    
    filename = os.path.basename(md_path)
    
    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")
    
    def save_chunk():
        nonlocal chunk_counter, current_text, current_heading, current_path
        text = "".join(current_text).strip()
        if text:
            chunk = ChunkMetadata(
                chunk_id=f"{filename}-chunk-{chunk_counter}",
                source_file=filename,
                heading=current_heading,
                heading_level=len(current_path) if current_path else 0,
                section_path=current_path.copy(),
                text=text
            )
            chunks.append(chunk.model_dump())
            chunk_counter += 1
        current_text = []

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            
            if level <= chunk_level:
                save_chunk()
                current_heading = heading_text
                current_path = current_path[:level-1] + [heading_text]
                current_text.append(line)
            else:
                current_text.append(line)
        else:
            current_text.append(line)
            
    save_chunk()
    
    os.makedirs(output_dir, exist_ok=True)
    name, _ = os.path.splitext(filename)
    output_path = os.path.join(output_dir, f"{name}.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    print(f"Saved {len(chunks)} chunks to {output_path}")
    return output_path
