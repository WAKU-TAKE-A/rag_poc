from pydantic import BaseModel
from typing import List

class ChunkMetadata(BaseModel):
    chunk_id: str
    source_file: str
    heading: str
    heading_level: int
    section_path: List[str]
    text: str
