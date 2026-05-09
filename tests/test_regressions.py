import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from whoosh.index import open_dir
from whoosh.qparser import EveryPlugin, QueryParser

import main
from src import parser as parser_module
from src import searcher


class FakeQdrantClient:
    def __init__(self):
        self.collection_exists = False
        self.points = []

    def delete_collection(self, collection_name):
        self.collection_exists = False
        self.points = []

    def create_collection(self, collection_name, vectors_config):
        self.collection_exists = True

    def upsert(self, collection_name, points):
        self.collection_exists = True
        self.points = list(points)

    def get_collection(self, collection_name):
        if not self.collection_exists:
            raise RuntimeError("missing collection")
        return {"name": collection_name}

    def query_points(self, collection_name, query, limit):
        point = MagicMock()
        point.payload = {"chunk_id": "vector-2"}
        return MagicMock(points=[point])


class RagPocRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

        for directory in ["input", "chunks", "parsed", "retrieval_debug"]:
            Path(directory).mkdir(parents=True, exist_ok=True)

        Path("config.json").write_text(
            json.dumps(
                {
                    "chunk_level": 2,
                    "search_limit": 3,
                    "llm_model": "gpt-4o-mini",
                    "llm_temperature": 0.3,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_sync_retries_when_embedding_failed_previously(self):
        Path("input/doc.md").write_text("# title\nbody\n", encoding="utf-8")

        args = type("Args", (), {})()

        with patch("main.convert_to_markdown", return_value="parsed/doc.md"), \
             patch("main.chunk_markdown", return_value="chunks/doc.json"), \
             patch("main.embed_chunks", side_effect=[False, True]), \
             patch("main.index_all_chunks"):
            main.sync_cmd(args)
            state = json.loads(Path("sync_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["files"]["input\\doc.md"]["status"], "chunked")

            main.sync_cmd(args)
            state = json.loads(Path("sync_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["files"]["input\\doc.md"]["status"], "embedded")

    def test_index_all_chunks_rebuilds_whoosh_without_duplicates(self):
        chunk_payload = [
            {
                "chunk_id": "sample.md-chunk-1",
                "source_file": "sample.md",
                "heading": "h1",
                "heading_level": 1,
                "section_path": ["h1"],
                "text": "alpha beta",
                "embedding": [0.1] * 1536,
            }
        ]
        Path("chunks/sample.json").write_text(
            json.dumps(chunk_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        fake_qdrant = FakeQdrantClient()
        with patch("src.searcher.get_qdrant_client", return_value=fake_qdrant):
            searcher.index_all_chunks()
            searcher.index_all_chunks()

        ix = open_dir("whoosh_index")
        with ix.searcher() as searcher_instance:
            parser = QueryParser("text", ix.schema)
            parser.add_plugin(EveryPlugin())
            results = searcher_instance.search(parser.parse("*"), limit=None)
            self.assertEqual(len(results), 1)

    def test_search_preserves_order_and_limit_without_reindexing(self):
        class FakeResult:
            def __init__(self, chunk_id):
                self.chunk_id = chunk_id

            def __getitem__(self, key):
                if key != "chunk_id":
                    raise KeyError(key)
                return self.chunk_id

        class FakeSearcherContext:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def search(self, query, limit):
                return [FakeResult("bm25-1"), FakeResult("shared"), FakeResult("bm25-3")]

        class FakeIndex:
            schema = object()

            def searcher(self):
                return FakeSearcherContext()

        fake_qdrant = FakeQdrantClient()
        fake_qdrant.collection_exists = True

        with patch("src.searcher.ensure_indexes_ready") as ensure_indexes_ready, \
             patch("src.searcher.open_dir", return_value=FakeIndex()), \
             patch("src.searcher.QueryParser") as query_parser_cls, \
             patch("src.searcher.Tokenizer") as tokenizer_cls, \
             patch("src.searcher.OpenAI") as openai_cls, \
             patch("src.searcher.get_qdrant_client", return_value=fake_qdrant), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            query_parser_cls.return_value.parse.return_value = "parsed-query"
            tokenizer_cls.return_value.tokenize.return_value = [
                type("Token", (), {"surface": "hello"})()
            ]
            openai_cls.return_value.embeddings.create.return_value = MagicMock(
                data=[MagicMock(embedding=[0.1] * 1536)]
            )
            fake_qdrant.query_points = MagicMock(
                return_value=MagicMock(
                    points=[
                        MagicMock(payload={"chunk_id": "shared"}),
                        MagicMock(payload={"chunk_id": "vector-2"}),
                        MagicMock(payload={"chunk_id": "vector-3"}),
                    ]
                )
            )

            results = searcher.search("hello")

        ensure_indexes_ready.assert_called_once()
        self.assertEqual(results, ["bm25-1", "shared", "bm25-3"])

    def test_cli_validators_reject_invalid_values(self):
        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["main.py", "split", "input/a.pdf", "--pages", "0"]):
                main.main()

        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["main.py", "config", "--chunk-level", "7"]):
                main.main()

        with self.assertRaises(ValueError):
            parser_module.split_pdf("input/a.pdf", pages_per_file=0)


if __name__ == "__main__":
    unittest.main()
