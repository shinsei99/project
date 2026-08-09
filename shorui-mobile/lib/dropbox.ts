import { Dropbox } from "dropbox";

/**
 * refreshトークン方式で Dropbox クライアントを作る。
 * アクセストークンは短命（4時間）なので、長期運用は refresh token 必須。
 * SDK が clientId/clientSecret/refreshToken から自動でアクセストークンを更新する。
 *
 * 必要な環境変数（Vercel の Environment Variables に設定）:
 *   DROPBOX_APP_KEY        … Dropbox アプリの App key
 *   DROPBOX_APP_SECRET     … Dropbox アプリの App secret
 *   DROPBOX_REFRESH_TOKEN  … scripts/get-refresh-token.mjs で取得
 */
export function getDropbox(): Dropbox {
  const clientId = process.env.DROPBOX_APP_KEY;
  const clientSecret = process.env.DROPBOX_APP_SECRET;
  const refreshToken = process.env.DROPBOX_REFRESH_TOKEN;
  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error(
      "Dropbox の環境変数が未設定です（DROPBOX_APP_KEY / DROPBOX_APP_SECRET / DROPBOX_REFRESH_TOKEN）"
    );
  }
  // Node 18+ のグローバル fetch を使う（Vercel の Node ランタイム）。
  return new Dropbox({ clientId, clientSecret, refreshToken });
}

/** 取込先のDropboxパス（ルート）。既定は /書類取込。 */
export const INBOX_ROOT = process.env.DROPBOX_INBOX_PATH || "/書類取込";
