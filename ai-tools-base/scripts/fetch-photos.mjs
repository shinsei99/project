/**
 * フリー写真を Openverse から取り込む。
 *
 * マルチプロダクション（agent-platform/tools/free_photos.py）と同じ経路。
 * ただしこのサイトでは **CC0 と パブリックドメイン（PDM）だけ**に絞っている。
 *
 * なぜ絞るか:
 *   CC BY / BY-SA は**出典表示が義務**で、表示を消した瞬間にライセンス違反になる。
 *   ページ構成を変えたときに表示が落ちる事故が起きうるので、
 *   **そもそも表示義務のない素材だけを取る**ことで構造的に防ぐ。
 *   （母数は減るが、鍵なしで完結し、事故らない方を選んだ）
 *
 * 守ること:
 *   - `license=cc0,pdm` で引く。NC（非営利限定）・ND（改変禁止）・BY系は取らない
 *   - 表示義務は無いが、作者・出典は記録しておく（後で出典を出したくなったとき用）
 *   - 人物が写った写真は肖像の扱いが別問題として残る。使う前に人が確認する
 *
 * なぜダウンロードしてローカルに置くか:
 *   外部ホストを直接参照すると、向こうが落ちた・URLが変わったときにサイトの見栄えが壊れる。
 *   取り込んでしまえばサイトは自己完結する（agent-platform も同じ理由でキャッシュしている）。
 *
 * 使い方: node scripts/fetch-photos.mjs
 * 出力  : public/photos/<slug>.jpg ＋ content/photo-credits.json
 */
import fs from "node:fs/promises";
import path from "node:path";

const ENDPOINT = "https://api.openverse.org/v1/images/";
const UA = { "User-Agent": "ai-tools-base/1.0 (free material search)" };
const MIN_BYTES = 40 * 1024;
/** 出典表示が要るライセンス。CC0/PDM に絞っているので通常は該当しないが、念のため判定する */
const NEEDS_CREDIT = ["by", "by-sa", "sa", "by-nd"];

/** 取りに行く絵柄。slug は記事・記録側から参照する名前 */
const WANTED = [
  { slug: "hero", q: "terminal code screen" },
  { slug: "claude-code-setup", q: "laptop keyboard developer" },
  { slug: "agent-era", q: "server room network" },
  { slug: "tool-comparison-2026", q: "workspace desk computer" },
  { slug: "prompt-patterns", q: "notebook writing desk" },
];

const OUT_DIR = path.join(process.cwd(), "public", "photos");
const CREDITS = path.join(process.cwd(), "content", "photo-credits.json");

async function search(query) {
  const url = new URL(ENDPOINT);
  url.searchParams.set("q", query);
  // CC0 と パブリックドメインのみ。**出典表示が不要な素材だけ**を取る
  url.searchParams.set("license", "cc0,pdm");
  url.searchParams.set("page_size", "8");
  const res = await fetch(url, { headers: UA });
  if (!res.ok) throw new Error(`Openverse ${res.status} (${query})`);
  const json = await res.json();
  return json.results ?? [];
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const credits = {};

  for (const { slug, q } of WANTED) {
    try {
      const results = await search(q);
      let saved = false;

      for (const item of results) {
        if (!item.url) continue;
        const img = await fetch(item.url, { headers: UA });
        if (!img.ok) continue;
        const buf = Buffer.from(await img.arrayBuffer());
        if (buf.byteLength < MIN_BYTES) continue; // 小さすぎるものは使わない

        await fs.writeFile(path.join(OUT_DIR, `${slug}.jpg`), buf);
        const code = String(item.license ?? "").toLowerCase();
        credits[slug] = {
          title: item.title ?? "",
          creator: item.creator ?? "",
          license: `${String(item.license ?? "").toUpperCase()} ${item.license_version ?? ""}`.trim(),
          licenseCode: code,
          needsCredit: NEEDS_CREDIT.includes(code),
          source: item.foreign_landing_url ?? item.source ?? "",
          provider: item.provider ?? "Openverse",
        };
        console.log(`✔ ${slug}  ${credits[slug].license}  ${credits[slug].creator}`);
        saved = true;
        break;
      }

      if (!saved) console.warn(`— ${slug}: 条件に合う画像が見つからず（SVGの表紙のままで動きます）`);
    } catch (e) {
      console.warn(`— ${slug}: ${e.message}（SVGの表紙のままで動きます）`);
    }
  }

  await fs.writeFile(CREDITS, JSON.stringify(credits, null, 2) + "\n");
  console.log(`\nクレジットを書き出しました: ${path.relative(process.cwd(), CREDITS)}`);
  const needing = Object.values(credits).filter((c) => c.needsCredit).length;
  if (needing > 0) {
    console.log(`※ ${needing}件が出典表示の必要な素材です（Credits コンポーネントが表示します）`);
  } else {
    console.log("※ すべて CC0 / パブリックドメイン。出典表示は不要です");
  }
}

main();
