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

        # Override project root for configuration
        os.environ["RAG_POC_PROJECT_ROOT"] = self.temp_dir.name

        # Override config and path related variables in loaded modules
        from src import config, state
        config.PROJECT_ROOT = self.temp_dir.name
        config._config_cache = None
        state.STATE_FILE = config.project_path("sync_state.json")

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
        if "RAG_POC_PROJECT_ROOT" in os.environ:
            del os.environ["RAG_POC_PROJECT_ROOT"]

    def test_sync_retries_when_embedding_failed_previously(self):
        Path("input/doc.md").write_text("# title\nbody\n", encoding="utf-8")

        args = type("Args", (), {})()

        with patch("src.parser.convert_to_markdown", return_value="parsed/doc.md"), \
             patch("src.chunker.chunk_markdown", return_value="chunks/doc.json"), \
             patch("src.embedder.embed_chunks", side_effect=[False, True]), \
             patch("src.searcher.index_all_chunks"):
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
        self.assertEqual(results, ["shared", "bm25-1", "vector-2"])

        # Verify debug output format and content
        debug_file = Path("retrieval_debug/search_hello.json")
        self.assertTrue(debug_file.exists())
        debug_data = json.loads(debug_file.read_text(encoding="utf-8"))
        self.assertIn("rrf_details", debug_data)

        shared_details = debug_data["rrf_details"]["shared"]
        self.assertAlmostEqual(shared_details["fused_score"], 1.0/62.0 + 1.0/61.0)
        self.assertEqual(shared_details["ranks"]["bm25"], 2)
        self.assertEqual(shared_details["ranks"]["vector"], 1)

    def test_cli_validators_reject_invalid_values(self):
        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["main.py", "split", "input/a.pdf", "--pages", "0"]):
                main.main()

        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["main.py", "config", "--chunk-level", "7"]):
                main.main()

        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["main.py", "config", "--chunk-max-chars", "-1"]):
                main.main()

        # Should not raise SystemExit for 0
        with patch("sys.argv", ["main.py", "config", "--chunk-max-chars", "0"]):
            main.main()

        with self.assertRaises(ValueError):
            parser_module.split_pdf("input/a.pdf", pages_per_file=0)

    def test_ask_dry_run_prints_prompt_without_calling_openai(self):
        chunk_payload = [
            {
                "chunk_id": "doc.md-chunk-1",
                "source_file": "doc.md",
                "heading": "h1",
                "heading_level": 1,
                "section_path": ["h1"],
                "text": "This is test context for dry-run.",
            }
        ]
        Path("chunks/doc.json").write_text(
            json.dumps(chunk_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch("src.searcher.search", return_value=["doc.md-chunk-1"]) as mock_search, \
             patch("src.answerer.OpenAI") as mock_openai_cls:

            from io import StringIO
            stdout_capture = StringIO()

            with patch("sys.stdout", new=stdout_capture):
                with patch("sys.argv", ["main.py", "ask", "test query?", "--dry-run"]):
                    main.main()

            output = stdout_capture.getvalue()

            mock_search.assert_called_once_with("test query?")
            mock_openai_cls.assert_not_called()

            self.assertNotIn("===", output)
            self.assertIn("This is test context for dry-run.", output)
            self.assertIn("test query?", output)

    def test_sync_state_absolute_paths_compatibility(self):
        from src.state import StateTracker
        from src.config import PROJECT_ROOT

        legacy_state = {
            "config_hash": "dummy_config_hash",
            "files": {
                os.path.join(PROJECT_ROOT, "input", "legacy_doc.md"): {
                    "hash": "legacy_hash",
                    "parsed_file": os.path.join(PROJECT_ROOT, "parsed", "legacy_doc.md"),
                    "chunk_file": os.path.join(PROJECT_ROOT, "chunks", "legacy_doc.json"),
                    "status": "embedded"
                }
            }
        }

        Path("sync_state.json").write_text(
            json.dumps(legacy_state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        tracker = StateTracker()

        expected_key = os.path.normpath("input/legacy_doc.md")
        expected_parsed = os.path.normpath("parsed/legacy_doc.md")
        expected_chunk = os.path.normpath("chunks/legacy_doc.json")

        record = tracker.get_file_record(expected_key)
        self.assertEqual(record.get("hash"), "legacy_hash")
        self.assertEqual(record.get("parsed_file"), expected_parsed)
        self.assertEqual(record.get("chunk_file"), expected_chunk)
        self.assertEqual(record.get("status"), "embedded")

        disk_state = json.loads(Path("sync_state.json").read_text(encoding="utf-8"))
        self.assertIn(expected_key, disk_state["files"])
        self.assertNotIn(os.path.join(PROJECT_ROOT, "input", "legacy_doc.md"), disk_state["files"])
        self.assertEqual(disk_state["files"][expected_key]["parsed_file"], expected_parsed)
        self.assertEqual(disk_state["files"][expected_key]["chunk_file"], expected_chunk)

    def test_sync_warns_on_critical_config_change_without_rebuild(self):
        state_data = {
            "config_hash": "old_hash",
            "files": {},
            "config": {
                "chunk_level": 2,
                "chunk_max_chars": 1000,
                "do_ocr": False,
                "pdf_split_pages": 20
            }
        }
        Path("sync_state.json").write_text(
            json.dumps(state_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        Path("config.json").write_text(
            json.dumps(
                {
                    "chunk_level": 3,
                    "chunk_max_chars": 1000,
                    "do_ocr": False,
                    "pdf_split_pages": 20
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        args = type("Args", (), {"rebuild": False})()

        with patch("src.logger.logger.warning") as mock_warn, \
             patch("src.parser.convert_to_markdown"), \
             patch("src.chunker.chunk_markdown"), \
             patch("src.embedder.embed_chunks"), \
             patch("src.searcher.index_all_chunks"):
            main.sync_cmd(args)

            mock_warn.assert_any_call(
                "Configuration affecting chunks/parsing has changed (e.g. chunk_level, chunk_max_chars, do_ocr, or pdf_split_pages). "
                "If you want to regenerate existing files and rebuild the index, please run: sync --rebuild"
            )

    def test_format_prompt_missing_placeholders(self):
        from src.answerer import format_prompt

        template_no_context = "Hello {query}"
        with patch("src.logger.logger.warning") as mock_warn:
            res = format_prompt(template_no_context, "mycontext", "myquery")
            self.assertEqual(res, "Hello myquery")
            mock_warn.assert_called_once_with("Prompt template is missing '{context}' placeholder.")

        template_no_query = "Hello {context}"
        with patch("src.logger.logger.warning") as mock_warn:
            res = format_prompt(template_no_query, "mycontext", "myquery")
            self.assertEqual(res, "Hello mycontext")
            mock_warn.assert_called_once_with("Prompt template is missing '{query}' placeholder.")

    def test_format_prompt_single_pass_no_recursion(self):
        from src.answerer import format_prompt

        template = "C={context}; Q={query}"
        context_val = "literal {query}"
        query_val = "real question"

        res = format_prompt(template, context_val, query_val)
        self.assertEqual(res, "C=literal {query}; Q=real question")


if __name__ == "__main__":
    unittest.main()
