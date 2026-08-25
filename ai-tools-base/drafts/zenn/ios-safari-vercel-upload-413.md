---
title: "iOS Safariから写真を送ると3枚目で必ず失敗する — Vercelの4.5MB上限と、縮小が黙って無効になる罠"
emoji: "📷"
type: "tech"
topics: ["nextjs", "vercel", "ios", "typescript", "javascript"]
published: true
---

紙の書類をスマホで撮って Dropbox に送るだけの Next.js アプリを、Vercel に置いて使っています。
撮影は iPhone、送信先は API Route (`/api/upload`)、そこから Dropbox API で保存する、という素直な作りです。

現場から来た報告はこうでした。

> **1枚か2枚なら送れる。3枚以上にすると必ず失敗する。**

原因は1つではなく、**iOS Safari 固有の罠が2つと、プラットフォームの上限が1つ**でした。
しかも2つ目と3つ目は、**エラーを出さずに無効化される**種類のものです。

## 罠1：iOS Safari は FormData のファイル名に非ASCIIが混ざると例外を投げる

最初に出ていたのは、送信ボタンを押した瞬間の例外です。

```
SyntaxError: The string did not match the expected pattern.
```

ネットワークにすら出ていません。`fetch` に到達する前に落ちています。
原因は `FormData.append` の第3引数、**ファイル名**でした。

```ts
shots.forEach((s) => fd.append("files", s.file, s.file.name));
```

iOS のカメラロールから選んだ写真は、ファイル名に日本語やアクセント記号が入ることがあります。
iOS Safari はこれを含むファイル名で送信しようとすると例外を投げます。

サーバー側は拡張子と自前の連番しか見ていないので、**元の名前を使う理由がありません**。
機械が付けた ASCII 名に置き換えました。

```ts
shots.forEach((s, i) => {
  const raw = (s.file.name.split(".").pop() || "").toLowerCase();
  const ext = /^[a-z0-9]{1,5}$/.test(raw) ? raw : "jpg";
  fd.append("files", s.file, `shot_${String(i + 1).padStart(2, "0")}.${ext}`);
});
```

これで例外は消えました。**が、3枚目からの失敗は残りました。**

## 罠2：Vercel のリクエストボディ上限 4.5MB

残っていたのは 413 でした。Vercel の Serverless Function には
**リクエストボディ 4.5MB** という上限があります。

スマホで撮った写真は 1枚あたり 2〜4MB あります。原寸のまま複数枚を1つの `FormData` に積めば、
**3枚目で必ず超える**という計算になります。「3枚以上で必ず失敗する」という報告の形とも合います。

ここで**症状の見え方を悪くしていたのが、レスポンスの読み方**でした。

```ts
const res = await fetch("/api/upload", { method: "POST", body: fd });
const j = await res.json();     // ← 413 のときプラットフォームが返すのはJSONではない
```

413 で返ってくるのは HTML やプレーンテキストなので、`res.json()` が
**パースエラーという無関係な例外**に化けます。画面には「送信に失敗しました」としか出ません。

先に文字列で受けて、状態コードで文言を分けるようにしました。

```ts
const text = await res.text();
let j: { ok?: boolean; error?: string; count?: number };
try {
  j = text ? JSON.parse(text) : {};
} catch {
  throw new Error(
    res.status === 413
      ? "写真の合計サイズが大きすぎます。枚数を減らして送ってください。"
      : `送信に失敗しました（${res.status}）`
  );
}
```

まずは送信前に縮小することにしました。長辺 1600px・JPEG 品質 0.72 です。
書類の文字は充分読めるまま 1枚あたり数百KBに収まります。

## 罠3：`createImageBitmap` は iOS Safari で失敗しやすく、失敗が握りつぶされる

縮小の実装は最初こうでした。

```ts
async function shrinkForUpload(file: File): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    // …canvas に描いて toBlob…
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;          // ★ ここ
  }
}
```

`createImageBitmap` は EXIF の向きまで面倒を見てくれるので第一候補でした。
ところが **iOS Safari では失敗しやすい**（特に HEIC）。

そして失敗したときの `catch` は **原本をそのまま返します**。
つまり「縮小が効かなかった端末では、何も縮まないまま 4.5MB に突っ込む」わけです。
コンソールには何も出ません。**直したはずなのに直っていない端末がある**、という一番厄介な形になります。

iOS で確実にデコードできる `<img>` + canvas 方式に変えました。
iOS は HEIC も `<img>` で読めますし、表示時に EXIF の向きを自動で正立させます。

```ts
async function shrinkForUpload(file: File): Promise<Blob> {
  const MAX_EDGE = 1600;
  const QUALITY = 0.72;
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("decode failed"));
      im.src = url;
    });
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    if (!iw || !ih) return file;

    const scale = Math.min(1, MAX_EDGE / Math.max(iw, ih));
    const w = Math.max(1, Math.round(iw * scale));
    const h = Math.max(1, Math.round(ih * scale));

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, w, h);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", QUALITY)
    );
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;
  } finally {
    URL.revokeObjectURL(url);
  }
}
```

なお `catch` で原本を返す設計そのものは残しています。
**縮小に失敗しても送信自体は成立させたい**からです。
危険なのはフォールバックがあることではなく、
**フォールバックしたことが誰にも伝わらないまま、上限に当たる設計のままでいること**でした。

## 本命の直し方：1枚＝1リクエストに分割する

縮小は対症療法です。**枚数が増えれば合計はいつか 4.5MB に届きます**。
10枚なら通っても、20枚ならまた同じ場所で止まります。

そこで **1枚＝1リクエスト**に分割しました。
分割すると、素直に作れば「1フォルダにまとまらない」問題が出ます。
サーバー側でフォルダ名を採番していたからです。

**束IDをクライアントで1回だけ作り、全リクエストで共有する**ようにしました。

```ts
// この束のフォルダ名を1回だけ作る。1枚ずつ送ってもPC側では1フォルダにまとまる。
function makeBatchId(property: string): string {
  const p = (n: number) => String(n).padStart(2, "0");
  const d = new Date();
  const stamp =
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  const slug =
    property.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_").trim().slice(0, 40) ||
    "未指定";
  return `${stamp}_${slug}`;
}
```

送信側のループはこうなります。進み具合が出るので、待たされている理由も分かるようになりました。

```ts
const batch = makeBatchId(property);
const total = shots.length;

for (let i = 0; i < total; i++) {
  setMsg({ ok: true, text: `送信中… ${i + 1}/${total} 枚` });

  const blob = await shrinkForUpload(shots[i].file);
  const fd = new FormData();
  fd.append("password", authPw || "");
  fd.append("property", property);
  fd.append("memo", memo);
  fd.append("batch", batch);
  fd.append("index", String(i + 1));
  fd.append("total", String(total));
  if (i === total - 1) fd.append("writeMeta", "1");  // 付帯情報は最後の1回だけ
  fd.append("files", blob, `shot_${String(i + 1).padStart(2, "0")}.jpg`);

  const res = await fetch("/api/upload", { method: "POST", body: fd });
  // …エラー処理は上と同じ。413 のときは「${i + 1}枚目が大きすぎて送れませんでした。」
}
```

受け取る側は、束IDが来ていればそれを使い、来ていなければ従来どおり自分で採番します。
**クライアントから来た文字列をそのままパスに使わない**ことだけ注意します。

```ts
// パス区切りや上位ディレクトリ指定を除いた安全な1階層のフォルダ名に丸める
function safeSegment(name: string): string {
  return (
    name
      .replace(/\.\.+/g, "_")
      .replace(/[\\/:*?"<>|]+/g, "_")
      .replace(/\s+/g, "_")
      .trim()
      .slice(0, 80) || "未指定"
  );
}

const batchRaw = ((form.get("batch") as string) || "").trim();
const batch = batchRaw ? safeSegment(batchRaw) : `${stamp(now)}_${slugify(property)}`;
const dir = `${INBOX_ROOT}/${batch}`;

// 通し番号はクライアントの index を優先（1枚ずつ送られてくるため）
const total = parseInt((form.get("total") as string) || "", 10) || files.length;
const startIndex = parseInt((form.get("index") as string) || "", 10) || 0;
let i = startIndex > 0 ? startIndex - 1 : 0;
```

付帯情報（`meta.json`）は**最後のリクエストだけ**が書きます。
毎回書くと枚数が途中の値で上書きされてしまうためです。

```ts
const writeMeta = batchRaw ? form.get("writeMeta") === "1" : true;
if (writeMeta) {
  const meta = { property, memo, capturedAt: now.toISOString(), count: total, source: "shorui-mobile" };
  await dbx.filesUpload({ path: `${dir}/meta.json`, /* … */ });
}
```

利用者の操作は「この束を送る」の一度きりのままです。
PC側から見た結果も従来と同じ、`<日時_物件名>/shot_01.jpg …` の1フォルダです。

## まとめ

同じところでつまずく人のために、順番に並べておきます。

| # | 症状 | 原因 | 直し方 |
|---|---|---|---|
| 1 | 送信の瞬間に `SyntaxError: The string did not match the expected pattern.` | iOS Safari は FormData のファイル名に非ASCIIが混ざると例外を投げる | ファイル名を ASCII 固定で付け直す |
| 2 | 3枚以上で必ず 413 | Vercel のリクエストボディ上限 4.5MB。写真は1枚2〜4MB | 送信前に長辺1600px・品質0.72へ縮小 |
| 2b | 413 の理由が画面に出ない | 413 の応答はJSONではないので `res.json()` がパースエラーに化ける | `res.text()` で受けてから `JSON.parse`、コード別の文言を出す |
| 3 | 縮小したのに端末によっては変わらない | `createImageBitmap` が iOS Safari で失敗し、`catch` が原本を返していた | `<img>` + canvas 方式へ（HEICも読め、向きも正立する） |
| 4 | 枚数を増やせばまた上限に当たる | 1リクエストに全部積む設計そのもの | 1枚＝1リクエストに分割し、束IDで同じフォルダに集約 |

教訓は2つです。

**上限は「超えないように詰める」より「原理的に当たらない形」に変えるほうが早い。**
縮小は枚数という変数を残しますが、分割はそれを消します。

そしてもう1つ。**`catch` で握りつぶしたフォールバックは、直したつもりの修正を静かに無効化します。**
今回いちばん時間を取られたのは 413 そのものではなく、
「縮小を入れたのに直らない端末がある」という、原因の見えない状態のほうでした。
