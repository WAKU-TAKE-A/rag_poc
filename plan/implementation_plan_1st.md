# RAG PoC CLI 実施計画書

本計画書は、『提案する計画書.md』に基づき、AIが自動で環境を構築し、コードを実装し、RAGのPoCをテストするための手順をまとめたものです。

## ワークフロー（AIによる自動実行）
1. **ディレクトリと環境のセットアップ**: プロジェクトディレクトリの作成と、Python仮想環境（venv）の構築。必要なライブラリ（`docling`, `whoosh`, `qdrant-client`, `openai`, `janome`）のインストール。
2. **ベースCLIの実装**: `main.py` を作成し、`argparse` を使用した基本コマンド（`parse`, `chunk`, `embed`, `search`）の構造を実装。
3. **パースモジュール**: `docling` を使用して、PDFやPPTXをMarkdownに変換する `parse` コマンドの実装。
4. **チャンクモジュール**: Markdownを見出し（heading）ごとに分割し、JSONとして保存する `chunk` コマンドの実装。
5. **埋め込み＆ベクトルDBモジュール**: OpenAIの `text-embedding-3-small` を使用してベクトル化を行う `embed` コマンドの実装。
6. **検索モジュール**: `Whoosh`（BM25）と `qdrant-client`（ローカルファイルモードによるベクトル検索）を組み合わせたハイブリッド検索の実装。日本語対応のために `Janome` を統合。
7. **検証**: サンプルファイルを使用してパイプライン全体を実行し、出力を確認。

## ユーザーによる確認が必要な事項
> [!IMPORTANT]
> - **OpenAI APIキー**: `embed` および `search` コマンド（ベクトル検索側）を実行するには、OpenAIのAPIキーが必要です。プロジェクトのルートディレクトリに `.env` ファイルを作成し、キーを設定していただく必要があります。
> - **Qdrantのセットアップ**: PoCをシンプルかつCLIベースで進めるため、Dockerを必要としない「ローカルモード」（ローカルフォルダ `./qdrant_data` への保存）を採用します。
> - **日本語対応**: Whooshでの日本語検索を可能にするため、形態素解析器 `Janome` を組み込み、インデックス時および検索時にトークナイズ（単語分割）を行います。

## 変更内容
### プロジェクトのセットアップ
- `requirements.txt` (新規)
- `.env.example` (新規)

### コアコード
- `main.py` (CLIエントリポイント)
- `src/parser.py` (Doclingの統合)
- `src/chunker.py` (Markdownの見出しベースのチャンク化)
- `src/embedder.py` (OpenAIの埋め込み)
- `src/searcher.py` (Whoosh + Qdrant のハイブリッド検索、Janome統合)
- `src/models.py` (Pydanticによるデータ構造定義)

## 検証計画
- `input/sample.md` を作成。
- CLIコマンドを順番に実行（`chunk` -> `search`）し、エラーなく動作することを確認。
- `search` の結果が `retrieval_debug/` に保存されることを確認。
