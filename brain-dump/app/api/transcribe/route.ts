import { getModel, hasApiKey, checkAccessCode } from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;

const TRANSCRIBE_PROMPT = `添付された音声を、日本語として自然な文章に文字起こししてください。

- 話された内容を忠実に書き起こす（勝手に要約・省略・脚色はしない）。
- 「えー」「あのー」などの言い淀みや意味のない相づちは適度に除き、読みやすくする。
- 句読点・改行を適切に入れる。話題が変わったら段落を分ける。
- 複数人が話している場合は、話者が変わるごとに改行する。
- どうしても聞き取れない箇所は「（聞き取れず）」と記す。
- 音声が無音・雑音のみで内容が無い場合は、空文字だけを出力する。

文字起こしした本文だけを出力してください。前置き・説明・注釈は一切不要です。`;

// ブラウザの MediaRecorder が出す代表的な音声形式（iOS=mp4, Chrome/Android=webm など）
const ALLOWED_MIME = [
  "audio/mp4",
  "audio/m4a",
  "audio/x-m4a",
  "audio/aac",
  "audio/webm",
  "audio/ogg",
  "audio/mpeg",
  "audio/mp3",
  "audio/wav",
  "audio/x-wav",
  "audio/3gpp",
];

type Audio = { data: string; mimeType: string };

/**
 * data URL（例: data:audio/webm;codecs=opus;base64,xxxx）を {data, mimeType} に分解。
 * codecs 等のパラメータは取り除き、Gemini に渡すベース MIME だけを残す。失敗時 null。
 */
function parseAudio(raw: string): Audio | null {
  if (typeof raw !== "string" || !raw) return null;
  const match = raw.match(/^data:(audio\/[a-zA-Z0-9.+-]+)[^,]*;base64,(.*)$/);
  if (!match) return null;
  return { mimeType: match[1].toLowerCase(), data: match[2] };
}

export async function POST(request: Request) {
  if (!checkAccessCode(request)) {
    return Response.json({ error: "アクセスコードが違います" }, { status: 401 });
  }
  if (!hasApiKey) {
    return Response.json(
      { error: "サーバーに GEMINI_API_KEY が設定されていません" },
      { status: 500 }
    );
  }

  let rawAudio = "";
  try {
    const body = await request.json();
    rawAudio = typeof body?.audio === "string" ? body.audio : "";
  } catch {
    return Response.json({ error: "リクエストが不正です" }, { status: 400 });
  }

  const audio = parseAudio(rawAudio);
  if (!audio) {
    return Response.json({ error: "音声データがありません" }, { status: 400 });
  }
  if (!ALLOWED_MIME.includes(audio.mimeType)) {
    return Response.json(
      { error: `対応していない音声形式です（${audio.mimeType}）` },
      { status: 400 }
    );
  }

  try {
    const model = getModel();
    const result = await model.generateContent({
      contents: [
        {
          role: "user",
          parts: [
            { inlineData: { data: audio.data, mimeType: audio.mimeType } },
            { text: TRANSCRIBE_PROMPT },
          ],
        },
      ],
      generationConfig: { temperature: 0.2 },
    });
    const text = result.response.text().trim();
    return Response.json({ text });
  } catch (err) {
    console.error("[/api/transcribe]", err);
    return Response.json(
      { error: "文字起こしに失敗しました。短く録り直すか、時間をおいてお試しください。" },
      { status: 502 }
    );
  }
}
