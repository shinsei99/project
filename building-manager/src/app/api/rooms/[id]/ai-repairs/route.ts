import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import { mkdtempSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const execFileAsync = promisify(execFile);
const CLAUDE_BIN = "/opt/homebrew/bin/claude";
const TIMEOUT_MS = 300_000;

const PROMPT = `
以下のファイル群は、賃貸物件の修繕・工事に関する書類です（請求書・領収書・工事見積書・施工報告書など）。
すべてのファイルを読み込み、各修繕記録を以下のJSON形式のみで返してください（説明文・コードブロック不要）。

{
  "repairs": [
    {
      "date": "YYYY-MM-DD（工事日・請求日など最も適切な日付）",
      "category": "水回り or エアコン or 内装 or 電気 or 設備 or その他",
      "description": "修繕内容の説明（簡潔に）",
      "contractor": "施工業者・請求元の名称",
      "costIncludingTax": 費用の数字のみ（税込）,
      "notes": "備考・工事番号・品番など（不明はnull）"
    }
  ],
  "extractionNotes": "抽出できなかった情報や特記事項があればここに記載（なければnull）"
}

注意事項:
- 1枚のファイルに複数の修繕記録がある場合はすべて配列に含める
- 金額は税込みの合計金額を数字のみで記載（¥マーク・カンマ不要）
- 税抜き金額しかない場合は1.1倍して税込換算する
- 日付は必ずYYYY-MM-DD形式に変換する
- repairs が空の場合は空配列 []
- JSONのみ返す（前後の説明文・\`\`\`json等のコードブロック不要）

対象ファイル: {filenames}
`.trim();

export async function POST(
  request: Request,
  props: { params: Promise<{ id: string }> },
) {
  const { id } = await props.params;
  const formData = await request.formData();
  const files = formData.getAll("files") as File[];

  if (!files.length) {
    return NextResponse.json({ error: "ファイルが選択されていません" }, { status: 400 });
  }

  const tmpDir = mkdtempSync(join(tmpdir(), `building-repair-${id}-`));
  const savedNames: string[] = [];

  try {
    for (const file of files) {
      const buf = Buffer.from(await file.arrayBuffer());
      const safeName = file.name.replace(/[^a-zA-Z0-9　-鿿\.\-_]/g, "_");
      writeFileSync(join(tmpDir, safeName), buf);
      savedNames.push(safeName);
    }

    const prompt = PROMPT.replace("{filenames}", savedNames.join("、"));

    const { stdout, stderr } = await execFileAsync(
      CLAUDE_BIN,
      ["-p", prompt, "--output-format", "json", "--tools", "Read", "--model", "sonnet"],
      { cwd: tmpDir, timeout: TIMEOUT_MS },
    );

    if (stderr) console.warn("[ai-repairs] stderr:", stderr.slice(0, 500));

    let claudeOutput: { result?: string; [k: string]: unknown };
    try {
      claudeOutput = JSON.parse(stdout);
    } catch {
      return NextResponse.json({ error: "Claude の出力が不正なJSON形式でした", raw: stdout.slice(0, 500) }, { status: 500 });
    }

    const resultText = claudeOutput.result ?? stdout;
    const jsonMatch = String(resultText).match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return NextResponse.json({ error: "AI の応答からJSONを抽出できませんでした", raw: String(resultText).slice(0, 500) }, { status: 500 });
    }

    const extracted = JSON.parse(jsonMatch[0]);
    return NextResponse.json({ success: true, data: extracted, files: savedNames });

  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  } finally {
    try { rmSync(tmpDir, { recursive: true }); } catch { /* ignore */ }
  }
}
