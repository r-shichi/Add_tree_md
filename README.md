# tree-md

カレントディレクトリ（または指定したディレクトリ）配下のフォルダ・ファイル構成を Markdown で出力する小さな CLI ツールです。外部パッケージは不要で、Python 3.9 以上で動作します。

## 特徴

- フォルダ構成をツリー形式、またはファイルへのリンク付きネストリスト形式で出力
- `.git` や `node_modules`、キャッシュ、仮想環境などを最初から除外
- 深さ制限、追加の除外パターン、ディレクトリのみの表示に対応
- `-o` で Markdown ファイルへ直接書き込み
- 出力は決定的（日時は `--timestamp` を付けた場合のみ）

## 使い方

```bash
# カレントディレクトリをツリー形式で表示
python tree_md.py

# 指定ディレクトリを Markdown ファイルへ書き出す
python tree_md.py path/to/project -o STRUCTURE.md

# リンク付きのネストリストにする
python tree_md.py --format list --title "プロジェクト構成"

# 深さ 2 まで、ログと一時フォルダを除いて表示
python tree_md.py --max-depth 2 --exclude "*.log" --exclude tmp
```

`pip install .` でインストールすると、`tree-md` コマンドとしても使えます。

## 出力例

### tree（デフォルト）

````markdown
# Directory Structure

```text
my-project/
├── src/
│   ├── main.py
│   └── utils.py
├── tests/
│   └── test_main.py
├── .gitignore
└── README.md
```

2 directories, 5 files
````

### list

````markdown
# Directory Structure

- **my-project/**
  - **src/**
    - [main.py](src/main.py)
    - [utils.py](src/utils.py)
  - **tests/**
    - [test_main.py](tests/test_main.py)
  - [.gitignore](.gitignore)
  - [README.md](README.md)

2 directories, 5 files
````

`list` 形式のリンクは、`-o` を指定した場合は出力ファイルの場所から、標準出力の場合はカレントディレクトリからの相対パスになります。

## オプション

| オプション | 説明 |
| --- | --- |
| `path` | 走査するディレクトリ（省略時はカレントディレクトリ） |
| `-o, --output FILE` | 標準出力ではなく FILE に書き込む（親ディレクトリは自動作成） |
| `--format {tree,list}` | 出力形式（デフォルト: `tree`） |
| `--title TEXT` | 見出し（デフォルト: `Directory Structure`） |
| `--no-title` | 見出しを省略 |
| `--max-depth N` | 再帰する深さ。`0` はルートのみ、`1` は直下まで |
| `-e, --exclude PATTERN` | 追加の除外パターン。繰り返し指定可。`/` を含む場合はルートからの相対パスに一致 |
| `--no-default-excludes` | デフォルトの除外を無効化 |
| `--dirs-only` | ディレクトリのみ表示 |
| `--timestamp` | 生成日時を見出しの下に追加 |
| `--version` | バージョンを表示 |

### デフォルトの除外対象

`.git`, `.hg`, `.svn`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `node_modules`, `.venv`, `venv`, `.DS_Store`, `Thumbs.db`

隠しファイルはデフォルトで表示されます（上記の除外対象を除く）。すべて表示したい場合は `--no-default-excludes` を使ってください。

## 補足

- シンボリックリンクには `@` を付け、ディレクトリへのリンクでも中には入りません。
- 走査対象の中に `-o` で出力する場合、出力ファイル自身は一覧に含めません。
- 読み取れないディレクトリがある場合は警告を stderr に出し、残りを出力します。
- 標準出力・出力ファイルともに UTF-8 で書き出します。

## テスト

```bash
python -m unittest discover -s tests -v
```

## ライセンス

[MIT](LICENSE)
