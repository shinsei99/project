import fs from "fs";
import path from "path";
import { prisma } from "@/lib/prisma";

// Dropbox 共有フォルダ内の「★要更新★」5点。随時同期で直接読む。
// （★必読★）新共有フォルダ 配下・ファイル名は固定運用。
export const DROPBOX_DIR =
  "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ";

export const SOURCE_FILES = {
  building: "★要更新★レントロール一覧（ビル）.xlsx",
  mansion: "★要更新★レントロール一覧（マンション）.xlsx",
  parking: "★要更新★レントロール一覧（駐車場他）.xlsx",
  ledger: "★要更新★管理物件台帳.xlsx",
} as const;

// レントロール契約日が空のときのプレースホルダ（Tenant.contractStart/End は必須）
const SENTINEL_START = new Date("2000-01-01T00:00:00Z");
const SENTINEL_END = new Date("2099-12-31T00:00:00Z");

const S = (v: unknown) => (v == null ? "" : String(v).trim());

// "26戸" "1,510,410" "〒536" 等から整数を取り出す（数字・カンマ・小数点・マイナスのみ残す）
function toInt(v: unknown): number | null {
  const s = S(v).replace(/[^0-9.\-]/g, "");
  if (!s || s === "-" || s === ".") return null;
  const n = Number(s);
  return Number.isFinite(n) ? Math.round(n) : null;
}

function parseDate(v: unknown): Date | null {
  const s = S(v);
  if (!s) return null;
  const m = s.match(/(\d{4})[\/\-年.](\d{1,2})[\/\-月.](\d{1,2})/);
  if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  const d = new Date(s);
  return isNaN(+d) ? null : d;
}

// 号室/区画Noから階を推定（101→1, 1203→12, "B1"/"Ａ棟"→1）
function deriveFloor(roomNo: string): number {
  const m = roomNo.match(/^(\d+)/);
  if (m) {
    const n = +m[1];
    return n >= 100 ? Math.floor(n / 100) : n || 1;
  }
  return 1;
}

type Counter = { created: number; updated: number };
const bump = (c: Counter, created: boolean) => (created ? c.created++ : c.updated++);

async function readWorkbook(fileName: string) {
  const XLSX = await import("xlsx");
  const full = path.join(DROPBOX_DIR, fileName);
  if (!fs.existsSync(full)) throw new Error(`ファイルが見つかりません: ${fileName}`);
  const buf = fs.readFileSync(full);
  return XLSX.read(buf, { type: "buffer", cellDates: true });
}

// シートを配列の配列で読む（1行目=物件名タイトル、2行目付近=見出し のため header:1 で読む）
async function sheetRows(ws: unknown): Promise<string[][]> {
  const XLSX = await import("xlsx");
  const raw = XLSX.utils.sheet_to_json(ws as never, {
    header: 1,
    raw: false,
    defval: "",
    blankrows: false,
  }) as unknown[][];
  return raw.map((r) => r.map((c) => S(c)));
}

// 見出し行を探して列インデックスを引く
function makeColFinder(rows: string[][]) {
  let hi = rows.findIndex((r) => r.some((c) => /号室|区画No|フロア/.test(c)));
  if (hi < 0) hi = rows.findIndex((r) => r.some((c) => /契約者/.test(c)));
  if (hi < 0) hi = 1;
  const header = rows[hi] ?? [];
  const col = (re: RegExp) => header.findIndex((h) => re.test(h));
  return { headerIndex: hi, col };
}

async function upsertBuildingByName(
  name: string,
  patch: Record<string, unknown>,
  bc: Counter,
): Promise<string> {
  const existing = await prisma.building.findFirst({ where: { name }, select: { id: true } });
  if (existing) {
    // 既存物件は空値で上書きしない（手入力・AI補完を守る）
    const data: Record<string, unknown> = {};
    for (const [k, val] of Object.entries(patch)) {
      if (k === "type") continue; // 種別は既存を尊重
      if (val !== null && val !== undefined && val !== "") data[k] = val;
    }
    if (Object.keys(data).length) await prisma.building.update({ where: { id: existing.id }, data });
    bump(bc, false);
    return existing.id;
  }
  const created = await prisma.building.create({
    data: { name, type: (patch.type as string) || "その他", ...patch } as never,
    select: { id: true },
  });
  bump(bc, true);
  return created.id;
}

// ---- 管理物件台帳 → Building マスター + Owner ----
async function syncLedger(report: SyncReport) {
  const wb = await readWorkbook(SOURCE_FILES.ledger);
  const XLSX = await import("xlsx");
  const ws = wb.Sheets["管理物件台帳"] ?? wb.Sheets[wb.SheetNames[0]];
  const rows = (
    XLSX.utils.sheet_to_json(ws as never, { header: 1, raw: false, defval: "", blankrows: false }) as unknown[][]
  ).map((r) => r.map((c) => S(c)));

  const header = rows.find((r) => r.some((c) => /物件名/.test(c))) ?? [];
  const hi = rows.indexOf(header);
  const idx = (re: RegExp) => header.findIndex((h) => re.test(h));
  const c = {
    type: idx(/種別/),
    name: idx(/物件名/),
    handling: idx(/分類/),
    address: idx(/住所/),
    zip: idx(/郵便番号/),
    built: idx(/築年/),
    structure: idx(/構造/),
    units: idx(/戸数/),
    access: idx(/交通/),
    owner: idx(/オーナー/),
  };
  if (c.name < 0) {
    report.warnings.push("管理物件台帳: 見出し（物件名）が見つからず、台帳の取り込みをスキップしました");
    return;
  }

  const at = (r: string[], i: number) => (i >= 0 ? S(r[i]) : "");
  const normType = (t: string) => {
    if (/駐車場|モータープール|パーキング|ガレージ/.test(t)) return "駐車場";
    if (/ビル/.test(t)) return "ビル";
    if (/マンション|ハイツ|ハイム|コーポ|ハウス|レジデンス/.test(t)) return "マンション";
    return ["マンション", "ビル", "駐車場", "その他"].includes(t) ? t : "その他";
  };

  for (const r of rows.slice(hi + 1)) {
    const name = at(r, c.name);
    const typeRaw = at(r, c.type);
    if (!name || /^■/.test(typeRaw) || /^■/.test(name)) continue; // 見出し・区切り行を除外

    // オーナー（あれば upsert してリンク）
    let ownerId: string | null = null;
    const ownerName = at(r, c.owner);
    if (ownerName) {
      const ex = await prisma.owner.findFirst({ where: { name: ownerName }, select: { id: true } });
      if (ex) ownerId = ex.id;
      else {
        const o = await prisma.owner.create({ data: { name: ownerName }, select: { id: true } });
        ownerId = o.id;
        report.owners.created++;
      }
    }

    const patch: Record<string, unknown> = {
      type: normType(typeRaw),
      handling: at(r, c.handling) || undefined,
      address: at(r, c.address) || undefined,
      structure: at(r, c.structure) || undefined,
      builtDate: at(r, c.built) || undefined,
      access: at(r, c.access) || undefined,
      totalUnits: toInt(at(r, c.units)) ?? undefined,
      ownerId: ownerId ?? undefined,
    };
    await upsertBuildingByName(name, patch, report.buildings);
  }
}

// ---- レントロール（1シート=1物件、行=部屋/区画） ----
async function syncRentRoll(fileName: string, buildingType: string, report: SyncReport) {
  const wb = await readWorkbook(fileName);
  for (const sheetName of wb.SheetNames) {
    const buildingName = sheetName.trim();
    if (!buildingName) continue;
    const rows = await sheetRows(wb.Sheets[sheetName]);
    const { headerIndex, col } = makeColFinder(rows);

    const c = {
      room: col(/号室|区画No|フロア/),
      status: col(/現況/),
      tenant: col(/契約者/),
      kubun: col(/区分/),
      rent: col(/家賃|賃料/),
      kyoueki: col(/共益費/),
      water: col(/水道/),
      deposit: col(/保証金|敷金/),
      contract: col(/契約日/),
      note: col(/備考/),
      total: col(/合計/),
    };

    const buildingId = await upsertBuildingByName(buildingName, { type: buildingType }, report.buildings);

    // セクション状態（1枚のシートに 居室→車庫→建物車庫 と縦に並ぶため）
    let currentSection: string | null = null; // null=居室（先頭セクション）
    let currentUnitType = "居室";
    let seq = 0;
    for (const r of rows.slice(headerIndex + 1)) {
      const at = (i: number) => (i >= 0 ? S(r[i]) : "");
      let roomNo = at(c.room);
      const tenantName = at(c.tenant);
      const statusText = at(c.status);

      if (/^合計/.test(roomNo) || /^合計/.test(tenantName)) continue; // 合計行

      // セクション見出し行の検出（例: 「マンション下車庫」「建物Ⅱ（車庫）」）。
      // 号室セルにラベルがあり、賃料/合計セルが見出し語（"賃料"/"合計"）＝再ヘッダの行。
      const looksLikeGarage = /車庫|駐車|ガレージ|バイク|倉庫|物置/.test(roomNo);
      const isReHeader = /賃料|家賃/.test(at(c.rent)) || /合計/.test(at(c.total));
      if (roomNo && !tenantName && (looksLikeGarage || isReHeader)) {
        currentSection = roomNo;
        currentUnitType = looksLikeGarage ? "車庫" : "居室";
        seq = 0;
        continue; // 見出し行自体はデータではない
      }

      // 空行（部屋番号も契約者も無い）は無視
      if (!roomNo && !tenantName) continue;
      // 部屋番号が空でも契約者がいる場合（例: 枚方招堤南町）は連番を振る
      if (!roomNo) roomNo = String(++seq);
      else seq++;

      // 車庫等サブセクションは番号が居室や別セクションと衝突するのでセクション名で名前空間化
      const storedRoomNo = currentSection ? `${currentSection}-${roomNo}` : roomNo;

      // ステータス: 現況列があれば従う。無いビルは契約者有無で判定
      let status = "募集中";
      if (statusText) status = /空/.test(statusText) ? "募集中" : "入居中";
      else status = tenantName ? "入居中" : "募集中";

      const rent = toInt(at(c.rent));
      const note = at(c.note) || undefined;
      const room = await prisma.room.upsert({
        where: { buildingId_roomNumber: { buildingId, roomNumber: storedRoomNo } },
        update: { status, rent: rent ?? undefined, floor: deriveFloor(roomNo), note, unitType: currentUnitType, section: currentSection },
        create: {
          buildingId,
          roomNumber: storedRoomNo,
          floor: deriveFloor(roomNo),
          layout: "—",
          status,
          rent: rent ?? undefined,
          note,
          unitType: currentUnitType,
          section: currentSection,
        },
        select: { id: true },
      });
      report.rooms.created++; // upsert は作成/更新の区別が取れないため合算件数として扱う

      // 入居中かつ契約者名あり → Tenant を upsert（既存の詳細は空で潰さない）
      if (status === "入居中" && tenantName) {
        const contractStart = parseDate(at(c.contract));
        const common = {
          name: tenantName,
          tenantKind: at(c.kubun) || undefined,
          condoFee: toInt(at(c.kyoueki)) ?? undefined,
          waterFee: toInt(at(c.water)) ?? undefined,
          depositAmount: toInt(at(c.deposit)) ?? undefined,
        };
        await prisma.tenant.upsert({
          where: { roomId: room.id },
          update: { ...common, ...(contractStart ? { contractStart } : {}) },
          create: {
            roomId: room.id,
            phone: "",
            guarantorCompany: "",
            guarantorContractNumber: "",
            contractStart: contractStart ?? SENTINEL_START,
            contractEnd: SENTINEL_END,
            ...common,
          },
        });
        report.tenants.created++;
      }
    }
  }
}

export type SyncReport = {
  ok: boolean;
  buildings: Counter;
  rooms: Counter;
  tenants: Counter;
  owners: Counter;
  warnings: string[];
  errors: string[];
  finishedAt: string;
};

export async function runRentRollSync(): Promise<SyncReport> {
  const report: SyncReport = {
    ok: true,
    buildings: { created: 0, updated: 0 },
    rooms: { created: 0, updated: 0 },
    tenants: { created: 0, updated: 0 },
    owners: { created: 0, updated: 0 },
    warnings: [],
    errors: [],
    finishedAt: "",
  };

  // 1) 台帳でマスター（種別・住所・オーナー等）を先に確定
  try {
    await syncLedger(report);
  } catch (e) {
    report.errors.push(`管理物件台帳: ${(e as Error).message}`);
  }

  // 2) レントロール3本で部屋・入居状況・家賃を反映
  const rolls: [keyof typeof SOURCE_FILES, string][] = [
    ["building", "ビル"],
    ["mansion", "マンション"],
    ["parking", "駐車場"],
  ];
  for (const [key, type] of rolls) {
    try {
      await syncRentRoll(SOURCE_FILES[key], type, report);
    } catch (e) {
      report.errors.push(`${SOURCE_FILES[key]}: ${(e as Error).message}`);
    }
  }

  report.ok = report.errors.length === 0;
  report.finishedAt = new Date().toISOString();
  return report;
}
