import os
import json
import glob
from openai import OpenAI
from src.logger import logger

def generate_answer(query: str, hit_ids: list[str]) -> str:
    logger.info(f"Generating answer for query: '{query}' using {len(hit_ids)} hits.")
    
    # 1. Load chunks to get text
    id_to_text = {}
    chunk_files = glob.glob("chunks/*.json")
    for file_path in chunk_files:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                chunks = json.load(f)
                for chunk in chunks:
                    id_to_text[chunk["chunk_id"]] = chunk["text"]
            except Exception as e:
                logger.error(f"Error loading chunk file {file_path}: {e}")
                
    # 2. Extract context
    context_texts = []
    for hit_id in hit_ids:
        if hit_id in id_to_text:
            context_texts.append(id_to_text[hit_id])
        else:
            logger.warning(f"Chunk ID {hit_id} not found in loaded chunks.")
            
    if not context_texts:
        logger.warning("No context text found for the hits.")
        return "該当する情報が見つからなかったため、回答を生成できませんでした。"
        
    context = "\n\n---\n\n".join(context_texts)
    
    # 3. Call OpenAI
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set. Cannot generate answer.")
        return "エラー: OPENAI_API_KEYが設定されていません。"
        
    client = OpenAI()
    
    prompt = f"""
以下の【コンテキスト】を元に、ユーザーの【質問】に日本語で回答してください。
コンテキストにない情報は勝手に推測して回答せず、「提供された情報からは分かりません」と答えてください。

【コンテキスト】
{context}

【質問】
{query}

【回答】
"""

    try:
        logger.info("Calling OpenAI chat completion (gpt-4o-mini)...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは提供されたコンテキストに忠実に答える優秀なAIアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        answer = response.choices[0].message.content
        logger.info("Successfully generated answer.")
        return answer
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return f"エラーが発生しました: {e}"
