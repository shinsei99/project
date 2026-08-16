/**
 * コンテンツ検証。**AIと自動化スクリプトが content/ を書き換える前提**なので、
 * 壊れたまま公開されないよう、公開前にここで落とす。
 *
 * 使い方: npm run validate
 *
 * 実装は Next.js のビルドを通さずに済ませたいので、ここでは形の検証だけを
 * 軽量に行う（zod の完全なスキーマは src/lib/schema.ts が持っており、
 * ページの読み出し時にも同じ検証が走る）。ここで見るのは「よくある壊れ方」:
 *   - JSONとして読めない
 *   - slug がファイル名と食い違う（リンク切れの原因になる）
 *   - works の visibility が無い／不正（**社内情報が公開される最悪の事故**）
 *   - 記事の frontmatter に必須項目が無い
 */
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const errors = [];
const warnings = [];

function fail(file, msg) {
  errors.push(`${file}: ${msg}`);
}

/** content/<dir> の JSON を1件ずつ見る */
function checkJsonDir(dir, check) {
  const target = path.join(ROOT, "content", dir);
  if (!fs.existsSync(target)) return [];
  const files = fs.readdirSync(target).filter((f) => f.endsWith(".json"));
  const items = [];
  for (const f of files) {
    const rel = `content/${dir}/${f}`;
    let data;
    try {
      data = JSON.parse(fs.readFileSync(path.join(target, f), "utf8"));
    } catch (e) {
      fail(rel, `JSONとして読めません — ${e.message}`);
      continue;
    }
    if (data.slug && data.slug !== f.replace(/\.json$/, "")) {
      fail(rel, `slug "${data.slug}" がファイル名と一致しません`);
    }
    check(data, rel);
    items.push(data);
  }
  return items;
}

// --- ツール ---
const tools = checkJsonDir("tools", (t, rel) => {
  for (const key of ["slug", "name", "vendor", "category", "summary", "pricing", "scores", "url"]) {
    if (t[key] === undefined) fail(rel, `必須項目 "${key}" がありません`);
  }
  if (t.scores) {
    for (const [k, v] of Object.entries(t.scores)) {
      if (typeof v !== "number" || v < 0 || v > 5) fail(rel, `scores.${k} は0〜5の数値にしてください（現在: ${v}）`);
    }
  }
  if (!t.review) warnings.push(`${rel}: review（評価の根拠）が空です。点数の根拠は書くこと`);
});

// --- 制作記録（ここが最重要） ---
const works = checkJsonDir("works", (w, rel) => {
  if (w.visibility !== "public" && w.visibility !== "internal") {
    fail(rel, `visibility は "public" か "internal" が必須です（社内情報の公開事故を防ぐ要）`);
  }
  if (w.visibility === "public") {
    // 公開するものだけ、個人情報の混入をざっと見る。
    // 「仕様」「様々」のような普通の語に当たらないよう、敬称は直前が漢字/カナのときだけ拾う。
    // 「仕様」「同様」など、敬称ではない一般語は先に除いてから見る（誤検知で警告が無視されるのを防ぐ）
    const text = JSON.stringify(w).replace(/仕様|同様|多様|様々|模様|異様|一様|様子|王様|神様/g, "");
    const patterns = [
      { re: /[一-龥ぁ-んァ-ヶ]{2,}(様|さん)/, label: "敬称つきの人名らしき記述" },
      { re: /0\d{1,4}-\d{1,4}-\d{3,4}/, label: "電話番号らしき数字" },
      { re: /〒\s*\d{3}-?\d{4}/, label: "郵便番号" },
      { re: /[\w.+-]+@[\w-]+\.[\w.]+/, label: "メールアドレス" },
    ];
    for (const { re, label } of patterns) {
      const hit = text.match(re);
      if (hit) {
        warnings.push(`${rel}: 公開設定だが${label}を含みます（"${hit[0]}"）。個人情報でないか確認してください`);
      }
    }
  }
});

// --- 記事（MDXの frontmatter） ---
const articlesDir = path.join(ROOT, "content", "articles");
let articleCount = 0;
if (fs.existsSync(articlesDir)) {
  for (const f of fs.readdirSync(articlesDir).filter((x) => x.endsWith(".mdx"))) {
    const rel = `content/articles/${f}`;
    const raw = fs.readFileSync(path.join(articlesDir, f), "utf8");
    const m = raw.match(/^---\n([\s\S]*?)\n---/);
    if (!m) {
      fail(rel, "frontmatter（先頭の --- で囲む部分）がありません");
      continue;
    }
    articleCount++;
    for (const key of ["slug", "title", "description", "kind", "publishedAt"]) {
      if (!new RegExp(`^${key}:`, "m").test(m[1])) fail(rel, `frontmatter に "${key}" がありません`);
    }
    const slug = m[1].match(/^slug:\s*(.+)$/m)?.[1].trim();
    if (slug && slug !== f.replace(/\.mdx$/, "")) {
      fail(rel, `slug "${slug}" がファイル名と一致しません`);
    }
  }
}

// --- 結果 ---
const publicWorks = works.filter((w) => w.visibility === "public").length;
console.log(
  `検証: ツール ${tools.length}件 / 記事 ${articleCount}件 / 制作記録 ${works.length}件（公開 ${publicWorks} / 社内 ${works.length - publicWorks}）`,
);

for (const w of warnings) console.warn(`⚠️  ${w}`);

if (errors.length > 0) {
  console.error(`\n❌ ${errors.length}件の問題があります:`);
  for (const e of errors) console.error(`   ${e}`);
  process.exit(1);
}
console.log("✅ 問題なし");
