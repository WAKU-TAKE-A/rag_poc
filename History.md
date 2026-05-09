# 更新履歴

## 2026-05-09 (続き)
- **OOM（メモリ不足）対策**:
  - **課題**: 100ページを超える巨大なPDFのパース時に、Doclingの解析処理がメモリ（16GB）を使い果たしてクラッシュした。
  - **解決策**:
    1. `config.json` に `do_ocr` 設定を追加し、デフォルトで **OCRを無効化** できるようにした。
    2. `pypdf` ライブラリを追加し、PDFを任意のページ数（デフォルト5ページ）ごとに分割する `split` コマンドを実装した。これにより、巨大なPDFも分割して安全に処理できるようになった。
- **Qdrant API仕様変更への対応**:
  - **課題**: `qdrant-client` の最新バージョンにおいて、`QdrantClient.search()` がエラー（AttributeError）になる問題が発生。
  - **解決策**: Qdrantの最新の推奨メソッドである `query_points()` を使用するように `src/searcher.py` を修正した。
- **OpenAI APIエラーのハンドリング**:
  - **課題**: APIキーの利用制限（Quota 429）発生時に、検索システム全体がクラッシュした。
  - **解決策**: OpenAIの呼び出し箇所に try-except を追加し、エラー発生時やAPIキー未設定時は自動的に「キーワード検索（BM25）のみ」で結果を返すように頑健化した。
- **RAG（回答生成）機能の追加**:
  - `src/answerer.py` を新規作成し、検索結果を元に OpenAI `gpt-4o-mini` を使って回答を生成する `ask` コマンドを実装。
  - 「情報がない場合は勝手に推測して答えない（ハルシネーション抑止）」プロンプト制御を組み込み、安全なRAGシステムを実現。

## 2026-05-09 (初期)
- **環境構築**: Python仮想環境（venv）の作成と、必要なライブラリ（`docling`, `whoosh`, `qdrant-client`, `openai`, `pydantic`, `python-dotenv`）のインストール。
- **コア機能実装**: `main.py`, `src/parser.py`, `src/chunker.py`, `src/embedder.py`, `src/searcher.py`, `src/models.py` の実装。
- **日本語対応**: 日本語形態素解析器 `Janome` を追加し、Whooshでの日本語検索が正しく動作するように改善。
- **ドキュメント作成**: `README.md`, `History.md` の作成、および `implementation_plan_1st.md` の日本語化。
