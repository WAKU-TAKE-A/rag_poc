import os
import json
import glob
from openai import OpenAI
from src.logger import logger

def _load_context_texts(hit_ids: list[str]) -> list[str]:
    remaining_ids = set(hit_ids)
    chunk_texts = {}

    for file_path in glob.glob("chunks/*.json"):
        if not remaining_ids:
            break

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                chunks = json.load(f)
                for chunk in chunks:
                    chunk_id = chunk["chunk_id"]
                    if chunk_id in remaining_ids:
                        chunk_texts[chunk_id] = chunk["text"]
                        remaining_ids.remove(chunk_id)
            except Exception as e:
                logger.error(f"Error loading chunk file {file_path}: {e}")

    context_texts = []
    for hit_id in hit_ids:
        text = chunk_texts.get(hit_id)
        if text is None:
            logger.warning(f"Chunk ID {hit_id} not found in loaded chunks.")
            continue
        context_texts.append(text)

    return context_texts

def generate_answer(query: str, hit_ids: list[str]) -> str:
    logger.info(f"Generating answer for query: '{query}' using {len(hit_ids)} hits.")
    
    # 1. Load config for LLM settings
    config_path = "config.json"
    llm_model = "gpt-4o-mini"
    llm_temperature = 0.3
    llm_system_prompt = "あなたは提供されたコンテキストに忠実に答える優秀なAIアシスタントです。"
    llm_user_prompt_template = "以下の【コンテキスト】を元に、ユーザーの【質問】に日本語で回答してください。コンテキストに直接的な答えがない場合でも、具体例や文脈から推測できる場合は、その旨を断った上で可能性のある回答を提示してください。\n\n【コンテキスト】\n{context}\n\n【質問】\n{query}\n\n【回答】"

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                llm_model = config.get("llm_model", llm_model)
                llm_temperature = config.get("llm_temperature", llm_temperature)
                llm_system_prompt = config.get("llm_system_prompt", llm_system_prompt)
                llm_user_prompt_template = config.get("llm_user_prompt_template", llm_user_prompt_template)
        except Exception as e:
            logger.error(f"Error loading config for LLM settings: {e}")

    # 2. Extract context
    context_texts = _load_context_texts(hit_ids)

    if not context_texts:
        logger.warning("No context text found for the hits.")
        return "該当する情報が見つからなかったため、回答を生成できませんでした。"
        
    context = "\n\n---\n\n".join(context_texts)
    
    # 4. Construct Prompt using template
    prompt = llm_user_prompt_template.replace("{context}", context).replace("{query}", query)
    
    # 5. Call OpenAI
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set. Cannot generate answer.")
        return "エラー: OPENAI_API_KEYが設定されていません。"
        
    client = OpenAI()
    
    try:
        logger.info(f"Calling OpenAI chat completion ({llm_model}, temp={llm_temperature})...")
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": llm_system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=llm_temperature
        )
        answer = response.choices[0].message.content
        logger.info("Successfully generated answer.")
        return answer
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return f"エラーが発生しました: {e}"
