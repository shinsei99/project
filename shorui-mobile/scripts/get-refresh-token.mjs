// Dropbox の refresh token を取得する（1回だけ実行）。
//
//   DROPBOX_APP_KEY=xxxx DROPBOX_APP_SECRET=yyyy npm run get-token
//
// 前提: Dropbox App Console でアプリを作成済み（scoped access / Full Dropbox、
//       権限 files.content.write と files.content.read を ON、Submit 済み）。
// 出力された DROPBOX_REFRESH_TOKEN を Vercel の環境変数に入れる。

import readline from "node:readline/promises";
import { stdin, stdout } from "node:process";

const key = process.env.DROPBOX_APP_KEY;
const secret = process.env.DROPBOX_APP_SECRET;
if (!key || !secret) {
  console.error("環境変数 DROPBOX_APP_KEY と DROPBOX_APP_SECRET を指定してください。");
  console.error("例) DROPBOX_APP_KEY=xxxx DROPBOX_APP_SECRET=yyyy npm run get-token");
  process.exit(1);
}

const scope = encodeURIComponent("files.content.write files.content.read");
const authUrl =
  `https://www.dropbox.com/oauth2/authorize?client_id=${key}` +
  `&response_type=code&token_access_type=offline&scope=${scope}`;

console.log("\n1) 次のURLをブラウザ（Dropboxログイン済み）で開いて「許可」を押す:\n");
console.log("   " + authUrl + "\n");
console.log("2) 画面に表示される認可コードをコピー\n");

const rl = readline.createInterface({ input: stdin, output: stdout });
const code = (await rl.question("3) 認可コードを貼り付けて Enter: ")).trim();
rl.close();

const body = new URLSearchParams({
  code,
  grant_type: "authorization_code",
  client_id: key,
  client_secret: secret,
});

const res = await fetch("https://api.dropboxapi.com/oauth2/token", {
  method: "POST",
  body,
});
const j = await res.json();

if (!res.ok || !j.refresh_token) {
  console.error("\n取得に失敗しました:", JSON.stringify(j, null, 2));
  process.exit(1);
}

console.log("\n✅ 取得できました。Vercel の Environment Variables にこれを設定:\n");
console.log("DROPBOX_REFRESH_TOKEN=" + j.refresh_token + "\n");
