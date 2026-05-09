# 更新履歴

## 2026-05-09
- **環境構築**: Python仮想環境（venv）の作成と、必要なライブラリ（`docling`, `whoosh`, `qdrant-client`, `openai`, `pydantic`, `python-dotenv`）のインストール。
- **コア機能実装**: `main.py`, `src/parser.py`, `src/chunker.py`, `src/embedder.py`, `src/searcher.py`, `src/models.py` の実装。
- **日本語対応**: 日本語形態素解析器 `Janome` を追加し、Whooshでの日本語検索が正しく動作するように改善（「RAG」での検索テスト成功）。
- **ドキュメント作成**: `README.md`, `History.md` の作成、および `implementation_plan_1st.md` の日本語化。
