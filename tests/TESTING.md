# テストガイド

## 概要

`tests/test_regressions.py` は、今回の安定性改善に対する回帰テストをまとめたファイルです。
主に `sync`、検索インデックス、検索結果の順序、CLI バリデーションの4系統を確認します。

## テスト対象

### 1. `sync` の状態遷移

- 埋め込み失敗時に `sync_state.json` の状態が `embedded` ではなく `chunked` で保存されること
- 次回の `sync` 実行時に、そのファイルが再処理されること

対象テスト:

- `test_sync_retries_when_embedding_failed_previously`

### 2. Whoosh インデックス再構築

- 再索引時に Whoosh 側へ同じチャンクが重複追加されないこと
- インデックスディレクトリの作り直しで件数が安定すること

対象テスト:

- `test_index_all_chunks_rebuilds_whoosh_without_duplicates`

### 3. 検索結果の順序と件数制限

- `search()` が毎回 `index_all_chunks()` を直接呼ばず、索引存在確認だけで済ませること
- BM25 とベクトル検索の結果を、順序を維持したまま重複排除できること
- `search_limit` を超えない件数で返ること

対象テスト:

- `test_search_preserves_order_and_limit_without_reindexing`

### 4. CLI 入力値バリデーション

- `split --pages 0` のような不正値を弾くこと
- `config --chunk-level 7` のような範囲外の見出しレベルを弾くこと
- `split_pdf()` 自体も `pages_per_file <= 0` を拒否すること

対象テスト:

- `test_cli_validators_reject_invalid_values`

## 実行コマンド

仮想環境の Python を使って実行します。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 想定結果

以下の4テストが `OK` で完了することを想定しています。

- `test_cli_validators_reject_invalid_values`
- `test_index_all_chunks_rebuilds_whoosh_without_duplicates`
- `test_search_preserves_order_and_limit_without_reindexing`
- `test_sync_retries_when_embedding_failed_previously`

## 補足

- テストは一時ディレクトリ上で実行されるため、既存の `input/` や `chunks/` の実データを直接変更しません。
- 外部 API や実 Qdrant への依存はモック化し、ローカルで再現可能な回帰テストにしています。
