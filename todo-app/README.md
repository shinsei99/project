# TODOアプリ

ブラウザで動く単純なTODOアプリ。追加・完了・削除ができる。バックエンドなし、`localStorage`に保存。

## 使い方

```bash
cd /Users/apple/todo-app
python3 -m http.server 8541
```

ブラウザで `http://localhost:8541` を開く。

## 構成

- `index.html` / `style.css` / `script.js` の3ファイルのみ
- データは `localStorage`（キー: `todo-app-items`）にJSON配列で保存。サーバー・DBなし
