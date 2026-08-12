import { NextRequest, NextResponse } from "next/server";
import { getDropbox, INBOX_ROOT } from "@/lib/dropbox";

// Dropbox SDK / Buffer を使うので Node ランタイム。写真数枚のアップに時間がかかるので延長。
export const runtime = "nodejs";
export const maxDuration = 60;

function stamp(now: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}` +
    `-${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}`
  );
}

function slugify(name: string): string {
  const s = name.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_").trim();
  return s.slice(0, 40) || "未指定";
}

// クライアントが送ってくる束IDを、パス区切りや上位ディレクトリ指定を除いた
// 安全な1階層のフォルダ名に丸める。
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

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();

    // 合言葉チェック（サーバー側。ここが本当の防御）
    const password = ((form.get("password") as string) || "");
    if (!process.env.APP_PASSWORD || password !== process.env.APP_PASSWORD) {
      return NextResponse.json({ error: "パスワードが違います" }, { status: 401 });
    }

    const property = ((form.get("property") as string) || "").trim();
    const memo = ((form.get("memo") as string) || "").trim();
    const files = form.getAll("files").filter((f): f is File => f instanceof File);

    if (files.length === 0) {
      return NextResponse.json({ error: "写真がありません" }, { status: 400 });
    }

    const dbx = getDropbox();
    const now = new Date();

    // 写真を1枚ずつ別リクエストで送ってきても同じフォルダにまとめられるよう、
    // クライアントが束IDを送ってくればそれを使う。無ければ従来どおりサーバーで採番。
    const batchRaw = ((form.get("batch") as string) || "").trim();
    const batch = batchRaw ? safeSegment(batchRaw) : `${stamp(now)}_${slugify(property)}`;
    const dir = `${INBOX_ROOT}/${batch}`;

    // 束全体の枚数と、このリクエストの通し番号（1始まり）。1枚ずつ送るとき用。
    const total = parseInt((form.get("total") as string) || "", 10) || files.length;
    const startIndex = parseInt((form.get("index") as string) || "", 10) || 0;

    let i = startIndex > 0 ? startIndex - 1 : 0;
    for (const file of files) {
      i++;
      const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
      const buf = Buffer.from(await file.arrayBuffer());
      await dbx.filesUpload({
        path: `${dir}/shot_${String(i).padStart(2, "0")}.${ext}`,
        contents: buf,
        mode: { ".tag": "add" },
        autorename: true,
        mute: true,
      });
    }

    // 付帯情報(meta.json)は、1枚ずつ送る場合は最後のリクエストだけで書く
    // （writeMeta=1）。単発リクエスト（従来方式）のときは常に書く。
    const writeMeta = batchRaw ? form.get("writeMeta") === "1" : true;
    if (writeMeta) {
      const meta = {
        property,
        memo,
        capturedAt: now.toISOString(),
        count: total,
        source: "shorui-mobile",
      };
      await dbx.filesUpload({
        path: `${dir}/meta.json`,
        contents: Buffer.from(JSON.stringify(meta, null, 2), "utf-8"),
        mode: { ".tag": "overwrite" },
        mute: true,
      });
    }

    return NextResponse.json({ ok: true, batch, count: files.length });
  } catch (e: unknown) {
    const msg =
      e instanceof Error ? e.message : typeof e === "string" ? e : "アップロードに失敗しました";
    console.error("upload error:", e);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
