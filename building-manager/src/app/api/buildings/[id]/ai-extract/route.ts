import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import { mkdtempSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { BUILDING_FIELDS } from "@/lib/buildingFields";
import { resolveClaudeBin } from "@/lib/claudeBin";

const execFileAsync = promisify(execFile);
const CLAUDE_BIN = resolveClaudeBin();
const TIMEOUT_MS = 300_000;
// 解析前の向き（縦横・回転）自動補正スクリプト（pdf_orient.py を利用）
const ORIENT_CLI = join(process.cwd(), "orient_cli.py");
const ORIENT_TIMEOUT_MS = 150_000;
// Office系（xlsx/xls/docx）をテキスト化するスクリプト（claude Read はバイナリ不可）
const SHEET_CLI = join(process.cwd(), "sheet_to_text.py");
const SHEET_TIMEOUT_MS = 60_000;
const OFFICE_EXT = /\.(xlsx|xls|docx)$/i;

/** スキャン書類の向きを正立補正する（PDF/画像）。失敗しても無視して続行。 */
async function correctOrientation(filePath: string): Promise<void> {
  try {
    await execFileAsync("python3", [ORIENT_CLI, filePath], { timeout: ORIENT_TIMEOUT_MS });
  } catch {
    /* 向き補正に失敗しても元ファイルで解析を続行 */
  }
}

/**
 * claude が読める形にファイルを整える。
 * - Office系(xlsx/xls/docx): テキスト(.txt)へ変換し、そのファイル名を返す
 * - PDF/画像: 向き補正して元のファイル名を返す
 * 変換に失敗した場合は元ファイル名を返す（claude 側でエラー説明が返る）。
 */
async function prepareForClaude(dir: string, name: string): Promise<string> {
  if (OFFICE_EXT.test(name)) {
    const txtName = `${name}.txt`;
    try {
      await execFileAsync("python3", [SHEET_CLI, join(dir, name), join(dir, txtName)], { timeout: SHEET_TIMEOUT_MS });
      return txtName;
    } catch (e) {
      console.warn("[building-ai-extract] sheet変換失敗:", name, e instanceof Error ? e.message : e);
      return name;
    }
  }
  await correctOrientation(join(dir, name));
  return name;
}

// BUILDING_FIELDS からAIに渡す項目説明を生成（単一情報源と同期）
function fieldSpecLine(f: (typeof BUILDING_FIELDS)[number]): string {
  const typeHint =
    f.type === "int" || f.type === "float"
      ? "数字のみ（単位・カンマ不要、不明はnull）"
      : f.type === "bool"
        ? "true / false（記載があれば。不明はnull）"
        : "文字列（不明はnull）";
  const scope = f.scope === "common" ? "共通" : `${f.scope}のみ`;
  return `  "${f.key}": ${typeHint},  // ${f.label}（${scope}）`;
}

const FIELD_BLOCK = BUILDING_FIELDS.map(fieldSpecLine).join("\n");

const PROMPT = `
以下のファイル群（最大5件）は、同一の物件（マンション／ビル／駐車場／その他）に関する複数の書類です（賃貸募集資料・マイソク・登記簿謄本・重要事項説明書・パンフレット等）。
すべてのファイルを突き合わせて総合的に判断し、物件管理システムの「建物情報」に登録すべき情報を1件分として統合抽出してください。
※部屋ごとの入居者情報ではなく、建物そのものの情報（構造・築年・戸数・設備・所有者など）を対象とします。

【複数書類の統合方針】
- 各項目は全ファイルを見て「最も確からしい1つの値」を決める（1ファイルに無くても他ファイルにあれば採用）。
- 情報源の優先順位（値が食い違う場合）:
  ・面積(敷地/延床)・所有者(オーナー)・構造・築年・戸数・権利関係 → 登記簿謄本を優先
  ・交通・共用設備・管理会社・管理費/修繕積立金・駐車場・用途地域 → 募集資料(マイソク)/重説を優先
- 値が食い違った場合は優先ソースを採用し、extractionNotes に「どの項目でどう食い違い、どちらを採ったか」を記録。
- 仲介業者・管理会社を所有者(オーナー)と混同しない。オーナーは登記簿の所有者欄のみ。
- 募集資料の賃料・共益費は特定の部屋・区画の金額であることが多い。建物全体の想定坪単価と断定できない場合は rentPerTsubo/commonFeePerTsubo に入れず null。
- 万一ファイル間で明らかに別建物が混在している場合は、最も情報量の多い建物を主として抽出し、その旨を extractionNotes に明記。

必ず以下のJSON形式のみで返してください。説明文・コードブロック(\`\`\`json等)は一切不要です。JSONだけを返してください。

{
  "building": {
    "name": "建物名称（不明はnull）",
    "type": "マンション / ビル / 駐車場 / その他 のいずれか（判別できなければnull）",
    "address": "所在地（不明はnull）",
${FIELD_BLOCK}
  },
  "extractionNotes": "抽出できなかった情報や特記事項（なければnull）"
}

注意事項:
- 情報が見つからない項目は必ずnull（空文字列ではなく）
- 金額・面積・戸数などは数字のみ（¥・㎡・カンマ・「戸」等の単位不要）
- builtDate（築年月）は "YYYY-MM" 形式（例: 1987年03月 → "1987-03"）
- structure（構造・規模）は「鉄骨造 9階建」のように構造＋階数をまとめて
- facilities（共用設備）はメールボックス・EV・オートロック等をカンマ区切りで
- autoLock/deliveryBox/hasElevator は共用設備の記載から true/false 判定
- オーナー名・住所は登記簿謄本の所有者欄から。電話/メールは書類に無ければnull
- マンション専用項目・ビル専用項目は、判別した種別に合うものだけ埋め、他はnullで可
- 返答はJSONのみ。前後の説明・\`\`\`json等のマークダウン不要

対象ファイル: {filenames}
`.trim();

function extractJson(text: string): unknown | null {
  const codeBlock = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (codeBlock) {
    try { return JSON.parse(codeBlock[1].trim()); } catch { /* fall through */ }
  }
  const braceMatch = text.match(/\{[\s\S]*\}/);
  if (braceMatch) {
    try { return JSON.parse(braceMatch[0]); } catch { /* fall through */ }
  }
  return null;
}

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

  const tmpDir = mkdtempSync(join(tmpdir(), `building-info-${id}-`));
  const savedNames: string[] = [];

  try {
    for (const file of files) {
      const buf = Buffer.from(await file.arrayBuffer());
      const safeName = file.name
        .replace(/[^\w　-鿿゠-ヿ぀-ゟ\.\-]/g, "_")
        .replace(/_+/g, "_");
      const savedPath = join(tmpDir, safeName);
      writeFileSync(savedPath, buf);
      const readableName = await prepareForClaude(tmpDir, safeName);
      savedNames.push(readableName);
    }

    const prompt = PROMPT.replace("{filenames}", savedNames.join("、"));

    const { stdout, stderr } = await execFileAsync(
      CLAUDE_BIN,
      ["-p", prompt, "--output-format", "json", "--tools", "Read", "--model", "sonnet", "--max-turns", "3"],
      { cwd: tmpDir, timeout: TIMEOUT_MS },
    );

    if (stderr) console.warn("[building-ai-extract] stderr:", stderr.slice(0, 500));

    let claudeOutput: { result?: string; [k: string]: unknown };
    try {
      claudeOutput = JSON.parse(stdout);
    } catch {
      return NextResponse.json({ error: "Claude の出力が不正なJSON形式でした", raw: stdout.slice(0, 300) }, { status: 500 });
    }

    const resultText = String(claudeOutput.result ?? stdout);
    const extracted = extractJson(resultText);

    if (!extracted) {
      console.error("[building-ai-extract] raw result:", resultText.slice(0, 1000));
      return NextResponse.json({
        error: "AIの応答からJSONを抽出できませんでした。ファイルが読み取れないか、AIが別形式で返答しました。",
        raw: resultText.slice(0, 500),
      }, { status: 500 });
    }

    return NextResponse.json({ success: true, data: extracted, files: savedNames });

  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  } finally {
    try { rmSync(tmpDir, { recursive: true }); } catch { /* ignore */ }
  }
}
