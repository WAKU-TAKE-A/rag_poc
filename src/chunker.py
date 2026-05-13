import json
import os
import re
from src.models import ChunkMetadata
from src.logger import logger

def _split_text_by_chars(text: str, max_chars: int) -> list[str]:
    """長すぎるテキストを句点（。）や改行で分割する最終フォールバック。"""
    if len(text) <= max_chars:
        return [text]

    parts = []
    remaining = text

    while len(remaining) > max_chars:
        # max_chars以内で最後の句点（。）を探す
        split_pos = remaining.rfind("。", 0, max_chars)
        if split_pos == -1:
            # 句点がなければ最後の改行を探す
            split_pos = remaining.rfind("\n", 0, max_chars)
        if split_pos == -1:
            # 改行もなければ最後のスペースを探す
            split_pos = remaining.rfind(" ", 0, max_chars)
        if split_pos == -1:
            # どれもなければ max_chars で強制的に切る
            split_pos = max_chars - 1

        parts.append(remaining[:split_pos + 1].strip())
        remaining = remaining[split_pos + 1:].strip()

    if remaining:
        parts.append(remaining)

    return parts

def _split_by_heading(text: str, level: int) -> list[dict]:
    """テキストを指定レベルの見出しで分割する。
    戻り値: [{"heading": str, "text": str}, ...]
    見出しが見つからなければ、元のテキスト1つだけを返す。
    """
    pattern = re.compile(r"^(#{" + str(level) + r"})\s+(.*)$", re.MULTILINE)

    matches = list(pattern.finditer(text))
    if not matches:
        return [{"heading": None, "text": text}]

    parts = []
    # 最初の見出しの前にテキストがあれば、それも保持する
    if matches[0].start() > 0:
        before_text = text[:matches[0].start()].strip()
        if before_text:
            parts.append({"heading": None, "text": before_text})

    for i, match in enumerate(matches):
        heading_text = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            parts.append({"heading": heading_text, "text": section_text})

    return parts

def _recursive_split(text: str, current_level: int, max_level: int, max_chars: int) -> list[str]:
    """見出しレベルを段階的に掘り下げて分割し、最後は文字数で分割する再帰関数。

    ## で分割（chunk_level）→ 1000文字超えたら ###で再分割
    → まだ超えてたら #### → ##### → 最終的に文字数で強制分割
    """
    # もう十分短ければそのまま返す
    if len(text) <= max_chars:
        return [text]

    # まだ掘れる見出しレベルがあれば、そのレベルで分割を試みる
    if current_level <= max_level:
        sub_parts = _split_by_heading(text, current_level)

        # 見出しが見つからなかった場合（1つだけで heading=None）
        if len(sub_parts) == 1 and sub_parts[0]["heading"] is None:
            # 次のレベルを試す
            return _recursive_split(text, current_level + 1, max_level, max_chars)

        # 見出しで分割できた場合、各パートを再帰的にさらに処理
        result = []
        for part in sub_parts:
            result.extend(_recursive_split(part["text"], current_level + 1, max_level, max_chars))
        return result

    # 見出しレベルを使い切った場合、文字数で強制分割（最終フォールバック）
    return _split_text_by_chars(text, max_chars)

def chunk_markdown(md_path: str, output_dir: str = "chunks", chunk_level: int = 2, chunk_max_chars: int = 0) -> str:
    logger.info(f"Chunking {md_path} at heading level {chunk_level}...")
    if chunk_max_chars > 0:
        logger.info(f"Adaptive split enabled: max {chunk_max_chars} chars per chunk (heading cascade ### -> #### -> ##### -> char split).")

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
            # 適応的分割：まず下位の見出しで分割を試み、最後に文字数分割
            if chunk_max_chars > 0 and len(text) > chunk_max_chars:
                # chunk_level の次のレベル（例: ##なら###）から掘り下げ開始
                start_level = chunk_level + 1
                max_level = 5  # ##### まで
                sub_texts = _recursive_split(text, start_level, max_level, chunk_max_chars)
                if len(sub_texts) > 1:
                    logger.info(f"  Chunk '{current_heading[:30]}...' ({len(text)} chars) -> split into {len(sub_texts)} sub-chunks.")
            else:
                sub_texts = [text]

            for i, sub_text in enumerate(sub_texts):
                suffix = f"-{i+1}" if len(sub_texts) > 1 else ""
                chunk = ChunkMetadata(
                    chunk_id=f"{filename}-chunk-{chunk_counter}{suffix}",
                    source_file=filename,
                    heading=current_heading,
                    heading_level=len(current_path) if current_path else 0,
                    section_path=current_path.copy(),
                    text=sub_text
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
        
    logger.info(f"Saved {len(chunks)} chunks to {output_path}")
    return output_path
