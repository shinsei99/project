/**
 * 制作記録の一次資料を、Claude Code の会話ログから拾い出す。
 *
 * **サイトの方針は「実際に投げた文面を載せる（体裁と語調だけ整えてよい）」。**
 * 記憶で書くと粒度が変わってしまい、記録としての価値が消える。
 * 実際の指示が残っているのは会話ログだけなので、ここが唯一の出典になる。
 *
 *   node scripts/harvest-prompts.mjs 間取り            # キーワードを含むセッションの発話を出す
 *   node scripts/harvest-prompts.mjs madori --first    # 各セッションの最初の1通だけ（着手の指示を探す用）
 *   node scripts/harvest-prompts.mjs "" --list         # セッション一覧だけ
 *
 * オプション:
 *   --dir <path>   会話ログの置き場（既定: ~/.claude/projects）
 *   --first        セッションごとに最初の発話だけ表示（kickoff のプロンプトを探すとき）
 *   --list         一覧のみ（本文を出さない）
 *   --max <n>      1発話あたりの表示文字数（既定 400）
 *
 * ⚠️ **出力には会社名・物件名・氏名がそのまま含まれる。**
 * ここからコピーして `content/works/*.json` に入れるときは、必ず伏せること
 * （`npm run validate` も敬称・電話番号・メールアドレスを検査するが、最後は人が見る）。
 */
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const args = process.argv.slice(2);
const keyword = (args[0] ?? "").toLowerCase();
const opt = (name, fallback = null) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? (args[i + 1] ?? true) : fallback;
};
const firstOnly = args.includes("--first");
const listOnly = args.includes("--list");
const maxChars = Number(opt("max", 400));
const root = String(opt("dir", path.join(os.homedir(), ".claude", "projects")));

/** 会話ログ（.jsonl）を再帰的に集める */
function findLogs(dir, depth = 2) {
  if (!fs.existsSync(dir) || depth < 0) return [];
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...findLogs(p, depth - 1));
    else if (e.name.endsWith(".jsonl")) out.push(p);
  }
  return out;
}

/**
 * 人が打った発話だけを取り出す。
 * ツール結果や `<system-reminder>` などの自動挿入は除く（人の指示ではないため）。
 */
function readUserMessages(file) {
  const msgs = [];
  let lines;
  try {
    lines = fs.readFileSync(file, "utf8").split("\n");
  } catch {
    return msgs;
  }
  for (const line of lines) {
    if (!line.trim()) continue;
    let d;
    try {
      d = JSON.parse(line);
    } catch {
      continue;
    }
    if (d.type !== "user") continue;
    const c = d.message?.content;
    let text = "";
    if (typeof c === "string") text = c;
    else if (Array.isArray(c)) text = c.filter((x) => x?.type === "text").map((x) => x.text).join("\n");
    text = text.trim();
    if (!text || text.startsWith("<")) continue; // 自動挿入のブロックは捨てる
    msgs.push({ text, at: d.timestamp ?? null });
  }
  return msgs;
}

const logs = findLogs(root);
if (logs.length === 0) {
  console.error(`会話ログが見つかりません: ${root}`);
  console.error("別のPCから持ってきた場合は --dir でその場所を指定してください。");
  process.exit(1);
}

const sessions = logs
  .map((file) => {
    const msgs = readUserMessages(file);
    const stat = fs.statSync(file);
    return { file, msgs, mtime: stat.mtime };
  })
  .filter((s) => s.msgs.length > 0)
  .filter((s) => !keyword || s.msgs.some((m) => m.text.toLowerCase().includes(keyword)))
  .sort((a, b) => a.mtime - b.mtime);

console.log(
  `会話ログ ${logs.length}本 / 該当 ${sessions.length}セッション` +
    (keyword ? `（キーワード: ${keyword}）` : "") +
    "\n⚠️ 出力には固有名詞が含まれます。公開前に必ず伏せてください。\n",
);

for (const s of sessions) {
  const day = s.mtime.toISOString().slice(0, 10);
  const hits = keyword ? s.msgs.filter((m) => m.text.toLowerCase().includes(keyword)) : s.msgs;
  console.log(`\n──────── ${day}  ${path.basename(s.file)}  （発話 ${s.msgs.length}件 / 該当 ${hits.length}件）`);
  if (listOnly) continue;
  const shown = firstOnly ? s.msgs.slice(0, 1) : hits;
  for (const m of shown) {
    const t = m.text.length > maxChars ? `${m.text.slice(0, maxChars)} …` : m.text;
    console.log(`\n  ▸ ${t.replace(/\n/g, "\n    ")}`);
  }
}
