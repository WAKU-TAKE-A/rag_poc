import os
import json
import glob
import shutil
import uuid
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
from whoosh.analysis import RegexTokenizer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from dotenv import load_dotenv
from janome.tokenizer import Tokenizer
from src.logger import logger
from src.config import load_config, project_path
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

def get_qdrant_client():
    return QdrantClient(path=project_path("qdrant_data"))

def index_all_chunks():
    logger.info("Indexing all chunks for search...")

    t = Tokenizer()

    # 1. Setup Whoosh
    schema = Schema(chunk_id=ID(stored=True), text=TEXT(stored=True, analyzer=RegexTokenizer(expression=r"\S+")))
    whoosh_dir = project_path("whoosh_index")
    if os.path.exists(whoosh_dir):
        shutil.rmtree(whoosh_dir)
    os.makedirs(whoosh_dir, exist_ok=True)
    ix = create_in(whoosh_dir, schema)

    writer = ix.writer()

    # 2. Setup Qdrant
    q_client = get_qdrant_client()
    collection_name = "chunks"

    # Recreate collection for PoC simplicity
    try:
        q_client.delete_collection(collection_name)
    except Exception:
        pass

    q_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    points = []

    # Read all chunks
    chunk_files = glob.glob(project_path("chunks/*.json"))
    for file_path in chunk_files:
        with open(file_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            for chunk in chunks:
                text = chunk["text"]
                tokenized_text = " ".join([token.surface for token in t.tokenize(text)])

                writer.add_document(chunk_id=chunk["chunk_id"], text=tokenized_text)

                if "embedding" in chunk:
                     point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"]))
                     payload = {k: v for k, v in chunk.items() if k != "embedding"}

                     points.append(PointStruct(
                         id=point_id,
                         vector=chunk["embedding"],
                         payload=payload
                     ))

    writer.commit()

    if points:
        q_client.upsert(
            collection_name=collection_name,
            points=points
        )

    logger.info(f"Indexed chunks into Whoosh and Qdrant.")

def _qdrant_collection_exists(collection_name: str) -> bool:
    try:
        q_client = get_qdrant_client()
        q_client.get_collection(collection_name)
        return True
    except Exception:
        return False

def ensure_indexes_ready():
    whoosh_dir = project_path("whoosh_index")
    if not os.path.exists(whoosh_dir) or not os.listdir(whoosh_dir):
        logger.info("Search index is missing. Rebuilding from chunks...")
        index_all_chunks()
        return

    if not _qdrant_collection_exists("chunks"):
        logger.info("Qdrant collection is missing. Rebuilding from chunks...")
        index_all_chunks()

def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> tuple[list[str], dict]:
    """
    Reciprocal Rank Fusion (RRF) to merge multiple ranked lists of hit IDs.

    Tie-breaker logic:
    1. Primary key: fused score (descending)
    2. Secondary key: best rank achieved (ascending, lower is better)
    3. Tertiary key: hit ID (alphabetical ascending)
    """
    scores = {}
    details = {}
    best_ranks = {}

    for list_idx, rank_list in enumerate(rankings):
        for rank_0indexed, hit_id in enumerate(rank_list):
            rank_1indexed = rank_0indexed + 1
            score_contribution = 1.0 / (k + rank_1indexed)

            if hit_id not in scores:
                scores[hit_id] = 0.0
                details[hit_id] = {
                    "fused_score": 0.0,
                    "ranks": {}
                }
                best_ranks[hit_id] = rank_1indexed
            else:
                if rank_1indexed < best_ranks[hit_id]:
                    best_ranks[hit_id] = rank_1indexed

            scores[hit_id] += score_contribution
            details[hit_id]["fused_score"] = scores[hit_id]
            source_name = "bm25" if list_idx == 0 else "vector"
            details[hit_id]["ranks"][source_name] = rank_1indexed

    def sort_key(hit_id):
        return (-scores[hit_id], best_ranks[hit_id], hit_id)

    sorted_hits = sorted(scores.keys(), key=sort_key)
    sorted_details = {hit_id: details[hit_id] for hit_id in sorted_hits}

    return sorted_hits, sorted_details

def search(query_str: str):
    logger.info(f"Searching for: '{query_str}'")

    config = load_config()
    search_limit = config.get("search_limit", 5)

    logger.info(f"Search limit set to: {search_limit}")

    # Ensure index artifacts exist.
    ensure_indexes_ready()

    # Initialize Janome for query
    t = Tokenizer()
    tokenized_query = " ".join([token.surface for token in t.tokenize(query_str)])
    logger.info(f"Tokenized query for BM25: '{tokenized_query}'")

    def run_bm25():
        logger.info("Starting BM25 search...")
        hits = []
        try:
            ix = open_dir(project_path("whoosh_index"))
            with ix.searcher() as searcher:
                query = QueryParser("text", ix.schema).parse(tokenized_query)
                results = searcher.search(query, limit=search_limit)
                for r in results:
                    hits.append(r["chunk_id"])
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
        logger.info(f"BM25 search completed. Hits: {len(hits)}")
        return hits

    def run_vector():
        logger.info("Starting Vector search...")
        hits = []
        if not os.environ.get("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set. Skipping vector search.")
            return hits
        try:
            client = OpenAI()
            logger.info("Calling OpenAI for query embedding...")
            response = client.embeddings.create(
                input=query_str,
                model="text-embedding-3-small"
            )
            query_vector = response.data[0].embedding

            logger.info("Querying Qdrant...")
            q_client = get_qdrant_client()
            q_results = q_client.query_points(
                collection_name="chunks",
                query=query_vector,
                limit=search_limit
            ).points

            for r in q_results:
                hits.append(r.payload["chunk_id"])
        except Exception as e:
            logger.warning(f"Vector search failed (maybe quota or API error): {e}")
            logger.warning("Falling back to keyword search only.")
        logger.info(f"Vector search completed. Hits: {len(hits)}")
        return hits

    # Run searches in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_bm25 = executor.submit(run_bm25)
        future_vector = executor.submit(run_vector)

        bm25_hits = future_bm25.result()
        embedding_hits = future_vector.result()

    # 3. Merge using RRF
    rrf_hits, rrf_details = reciprocal_rank_fusion([bm25_hits, embedding_hits], k=60)
    merged_hits = rrf_hits[:search_limit]

    # Save debug info
    debug_info = {
        "query": query_str,
        "tokenized_query": tokenized_query,
        "bm25_hits": bm25_hits,
        "embedding_hits": embedding_hits,
        "merged_hits": merged_hits,
        "rrf_details": {hit_id: rrf_details[hit_id] for hit_id in merged_hits}
    }

    os.makedirs(project_path("retrieval_debug"), exist_ok=True)
    safe_query = "".join([c if c.isalnum() else "_" for c in query_str])
    debug_path = project_path(f"retrieval_debug/search_{safe_query}.json")

    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(debug_info, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved retrieval debug to {debug_path}")
    logger.info(f"BM25 hits: {len(bm25_hits)}")
    logger.info(f"Embedding hits: {len(embedding_hits)}")
    logger.info(f"Merged hits: {len(merged_hits)}")

    return merged_hits
