# RAG PoC CLI (v0.9.0)

本プロジェクトは、RAG (Retrieval Augmented Generation) の内部処理を可視化・説明可能にすることを目的とした、CLI（コマンドライン）ベースのPoC（概念実証）環境です。

ブラックボックスになりがちなRAGの「パース」「チャンク化」「検索」「回答生成」の各工程を分離し、それぞれの中間成果物やデバッグ情報をファイルとして保存することで、処理の透明性を確保しています。

## 主な機能と特徴

- **差分更新 (`sync`)**: ファイルのハッシュ値を管理し、変更のあったファイルだけを自動でパース・チャンク化・埋め込み・インデックス更新します。
- **ハイブリッド検索**: キーワード検索（BM25）とベクトル検索を組み合わせた検索が可能です。
- **日本語対応**: キーワード検索エンジンに形態素解析器（Janome）を組み込んでおり、日本語の文章でも適切に検索できます。
- **柔軟な入力**: 各コマンドは、単一のファイルだけでなく、**フォルダを指定しての一括処理（バッチ処理）**にも対応しています。
- **可視化**: 検索結果のヒット理由や、各エンジンのスコア（またはヒット有無）をデバッグJSONとして出力します。
- **省メモリ設計**: デフォルトでは重いOCR処理をオフにしており、巨大なPDFは自動（または手動）で分割して処理することが可能です。
- **回答生成 (RAG)**: 検索結果を元に、LLM（OpenAI）が事実に基づいた回答を生成します。

## システム構成

- **文書解析 (Parse)**: [Docling](https://github.com/DS4SD/docling) (PDF, PPTX などを Markdown に変換)
- **チャンク化 (Chunk)**: Markdown の見出し（Heading）ベースの独自ロジック
- **キーワード検索 (BM25)**: [Whoosh](https://whoosh.readthedocs.io/) + [Janome](https://mocobeta.github.io/janome/)
- **ベクトル検索 (Vector)**: [Qdrant](https://qdrant.tech/) (ローカルファイルモード) + OpenAI `text-embedding-3-small`
- **回答生成 (Generation)**: OpenAI `gpt-4o-mini`

## ディレクトリ構成

```text
project/
├ input/               # 元データ（PDF, PPTX, MD など）を配置
├ parsed/              # パースされ、Markdown化されたテキスト
├ chunks/              # チャンク化され、メタデータが付与されたJSON
├ retrieval_debug/     # 検索時のデバッグ情報（ヒットしたIDなど）
├ logs/                # 実行ログ（app.log）
├ src/                 # 各処理のソースコード
├ plan/                # 仕様書や計画書
├ qdrant_data/         # Qdrantのローカルデータベース
├ config.json          # システム設定ファイル
└ main.py              # CLIエントリポイント
```

## セットアップ手順

### 1. Python環境の準備
Python 3.10以降が必要です。

```bash
# 仮想環境の作成
python -m venv .venv

# 仮想環境の有効化（Windowsの場合）
.\.venv\Scripts\activate

# ライブラリのインストール
python -m pip install -r requirements.txt
```

### 2. 環境変数の設定
ベクトル検索および回答生成（OpenAI）を使用する場合、プロジェクトルートに `.env` ファイルを作成し、OpenAIのAPIキーを設定してください。

```text
OPENAI_API_KEY=your_openai_api_key_here
```

---

## 使い方（基本ワークフロー）

### 🌟 推奨：一括同期コマンド (`sync`)
`input/` フォルダにドキュメントを配置し、以下のコマンドを実行するだけで、全自動で追加・変更されたファイルのみを処理し、検索可能な状態にします。

```bash
.\.venv\Scripts\python.exe main.py sync
```

### 質問と回答生成 (`ask`)
質問を入力すると、検索と回答生成を自動で行います。

```bash
.\.venv\Scripts\python.exe main.py ask "Http通信の仕様について教えて"
```

---

## 使い方（ステップ別マニュアル実行）
トラブルシューティングや、特定のステップだけをやり直したい場合は、以下のコマンドを個別に実行できます。

### Step 1: PDFの分割 (`split`)
巨大なPDFでメモリ不足になる場合、あらかじめ分割します。
```bash
.\.venv\Scripts\python.exe main.py split input/sample.pdf --pages 5
```

### Step 2: パース (`parse`)
```bash
.\.venv\Scripts\python.exe main.py parse input/
```

### Step 3: チャンク化 (`chunk`)
```bash
.\.venv\Scripts\python.exe main.py chunk parsed/
```

### Step 4: 埋め込み (`embed`)
```bash
.\.venv\Scripts\python.exe main.py embed chunks/
```

## 設定の変更 (`config`)
プロンプトや温度、検索件数などを変更できます。

```bash
# 現在の設定を確認
.\.venv\Scripts\python.exe main.py config

# 検索取得件数を10件に変更
.\.venv\Scripts\python.exe main.py config --search-limit 10

# AIの温度（ランダム性）を0.7に上げる
.\.venv\Scripts\python.exe main.py config --llm-temperature 0.7
```
