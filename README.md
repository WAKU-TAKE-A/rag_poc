# RAG PoC CLI

本プロジェクトは、RAG (Retrieval Augmented Generation) の内部処理を可視化・説明可能にすることを目的とした、CLI（コマンドライン）ベースのPoC（概念実証）環境です。

ブラックボックスになりがちなRAGの「パース」「チャンク化」「検索」の各工程を分離し、それぞれの中間成果物やデバッグ情報をファイルとして保存することで、処理の透明性を確保しています。

## 主な機能と特徴

- **ハイブリッド検索**: キーワード検索（BM25）とベクトル検索を組み合わせた検索が可能です。
- **日本語対応**: キーワード検索エンジンに形態素解析器（Janome）を組み込んでおり、日本語の文章でも適切に検索できます。
- **柔軟な入力**: 各コマンドは、単一のファイルだけでなく、**フォルダを指定しての一括処理（バッチ処理）**にも対応しています。
- **可視化**: 検索結果のヒット理由や、各エンジンのスコア（またはヒット有無）をデバッグJSONとして出力します。

## システム構成

- **文書解析 (Parse)**: [Docling](https://github.com/DS4SD/docling) (PDF, PPTX などを Markdown に変換)
- **チャンク化 (Chunk)**: Markdown の見出し（Heading）ベースの独自ロジック
- **キーワード検索 (BM25)**: [Whoosh](https://whoosh.readthedocs.io/) + [Janome](https://mocobeta.github.io/janome/)
- **ベクトル検索 (Vector)**: [Qdrant](https://qdrant.tech/) (ローカルファイルモード) + OpenAI `text-embedding-3-small`

## ディレクトリ構成

```text
project/
├ input/               # 元データ（PDF, PPTX, MD など）を配置
├ parsed/              # パースされ、Markdown化されたテキスト
├ chunks/              # チャンク化され、メタデータが付与されたJSON
├ retrieval_debug/     # 検索時のデバッグ情報（ヒットしたIDなど）
├ src/                 # 各処理のソースコード
├ qdrant_data/         # Qdrantのローカルデータベース
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

### 2. 環境変数の設定（ベクトル検索用）
ベクトル検索（OpenAI）を使用する場合、プロジェクトルートに `.env` ファイルを作成し、OpenAIのAPIキーを設定してください。
（設定しない場合でも、キーワード検索のみで動作します）

```text
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 環境の再現性について
本プロジェクトは、`requirements.txt` によって依存ライブラリの構成を管理しています。
別のPCや環境で**全く同じ環境を再現する**には、必ず上記の手順（仮想環境の作成 → `pip install -r requirements.txt`）を行ってください。これにより、ライブラリの差異による動作不良を防ぎ、チーム内や異なる環境でも同様の挙動を保証できます。

---

## 使い方（基本ワークフロー）

RAGのデータ準備から検索までは、以下の4つのステップ（コマンド）を順番に実行します。
すべてのコマンドで、ファイルパスの代わりに **フォルダパスを指定すると、その中の対象ファイルを一括処理** します。

### Step 1: パース (`parse`)
入力文書（PDFやPowerPointなど）を読み込み、共通の中間形式である Markdown に変換します。

```bash
# ファイル単体の処理
.\.venv\Scripts\python.exe main.py parse input/sample.pdf

# フォルダ内の一括処理
.\.venv\Scripts\python.exe main.py parse input/
```
- **出力先**: `parsed/` フォルダに `.md` ファイルが生成されます。
- ※Markdownファイル（.md）をそのまま使う場合は、このステップをスキップして `parsed/` に直接配置しても構いません。

### Step 2: チャンク化 (`chunk`)
Markdownファイルを読み込み、見出し（Heading）を基準に適切なサイズに分割（チャンク化）します。

```bash
# ファイル単体の処理
.\.venv\Scripts\python.exe main.py chunk parsed/sample.md

# フォルダ内の一括処理
.\.venv\Scripts\python.exe main.py chunk parsed/

# オプション: チャンク化する見出しレベル（デフォルトは2: h2）
.\.venv\Scripts\python.exe main.py chunk parsed/sample.md --level 3
```
- **出力先**: `chunks/` フォルダに `.json` ファイルが生成されます。各チャンクにはIDや見出しの階層情報（メタデータ）が付与されます。

### Step 3: 埋め込み (`embed`)
※このステップはOpenAIのAPIキーが必要です。
チャンク化されたJSONファイルを読み込み、各テキストのベクトル（意味の数値化）を取得してJSONに追記します。

```bash
# ファイル単体の処理
.\.venv\Scripts\python.exe main.py embed chunks/sample.json

# フォルダ内の一括処理
.\.venv\Scripts\python.exe main.py embed chunks/
```
- **出力先**: `chunks/` 内の既存のJSONファイルが更新され、各チャンクに `"embedding"` フィールドが追加されます。

### Step 4: 検索 (`search`)
質問（クエリ）を入力して、該当するチャンクを検索します。

```bash
.\.venv\Scripts\python.exe main.py search "タイムアウトの変更方法"
```
- **処理内容**:
  1. `chunks/` フォルダ内のすべてのデータを読み込み、Whoosh（キーワード）とQdrant（ベクトル）のデータベースを自動で構築・更新します。
  2. 入力されたクエリで両方のエンジンから検索を行い、結果を統合します。
- **出力先**: 検索の実行結果（ヒットしたチャンクのID一覧など）が `retrieval_debug/` に保存されます。これを見ることで、「なぜその結果になったか」を追えるようになっています。
