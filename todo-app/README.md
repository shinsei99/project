# TODOアプリ

ブラウザで動く単純なTODOアプリ。ログイン後、追加・完了・削除ができる。バックエンドなし、`localStorage`に保存。

当面ローカル利用のみ・公開しない方針（2026-08-17）。

## 使い方

```bash
cd /Users/apple/todo-app
python3 -m http.server 8541
```

ブラウザで `http://localhost:8541` を開く。初回は「新規登録」からユーザー名・パスワード（4文字以上）を登録するとそのままログインする。

## ログイン機能について（重要な制約）

- バックエンド・DBを持たない静的アプリのため、**認証情報もブラウザの`localStorage`内で完結**する
  クライアントサイド認証（本物のサーバー認証ではない）。同一ブラウザ内での利用者分離が目的で、
  第三者からの不正アクセスを防ぐセキュリティ機能としては使わないこと。
- パスワードは平文保存ではなく、ユーザーごとのランダムsalt + SHA-256ハッシュ化して保存
  （`crypto.subtle.digest`使用。ブラウザの Secure Context 制約上、`http://localhost` か `https://` でのみ動作）。
- TODOはユーザー名ごとに別キーで保存されるため、ユーザーが違えばリストも別になる。

## 構成

- `index.html` / `style.css` / `script.js` の3ファイルのみ
- `localStorage`の保存キー:
  - `todo-app-users` … `{ username: { salt, hash } }`
  - `todo-app-session` … 現在ログイン中のユーザー名（ログアウトで削除）
  - `todo-app-items::<username>` … そのユーザーのTODO配列（旧`todo-app-items`から移行、ユーザー別に分離）
- サーバー・DBなし
