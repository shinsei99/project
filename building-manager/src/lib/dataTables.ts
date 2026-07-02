// Excelエクスポート/インポートの列定義を一元管理する。
// エクスポート・インポート双方をこの定義から駆動し、往復の整合を保つ。
import { BUILDING_FIELDS } from "./buildingFields";

export type ColKind = "string" | "int" | "float" | "bool" | "date";
export interface Col {
  header: string;
  key: string;
  kind: ColKind;
  readOnly?: boolean; // 表示専用（インポート時は無視）
}

// 建物（Building）
export const BUILDING_COLS: Col[] = [
  { header: "ID", key: "id", kind: "string" },
  { header: "種別", key: "type", kind: "string" },
  { header: "管理/仲介", key: "handling", kind: "string" },
  { header: "名称", key: "name", kind: "string" },
  { header: "住所", key: "address", kind: "string" },
  ...BUILDING_FIELDS.map((f): Col => ({ header: f.label, key: f.key, kind: f.type as ColKind })),
  { header: "オーナーID", key: "ownerId", kind: "string" },
];

// オーナー（Owner）
export const OWNER_COLS: Col[] = [
  { header: "ID", key: "id", kind: "string" },
  { header: "法人名", key: "company", kind: "string" },
  { header: "名前", key: "name", kind: "string" },
  { header: "住所", key: "address", kind: "string" },
  { header: "電話番号", key: "phone", kind: "string" },
  { header: "FAX", key: "fax", kind: "string" },
  { header: "メール", key: "email", kind: "string" },
  { header: "備考", key: "note", kind: "string" },
];

// 部屋（Room）— 部屋＋入居者シートの部屋側
export const ROOM_COLS: Col[] = [
  { header: "部屋ID", key: "id", kind: "string" },
  { header: "建物ID", key: "buildingId", kind: "string" },
  { header: "建物名", key: "buildingName", kind: "string", readOnly: true },
  { header: "部屋番号", key: "roomNumber", kind: "string" },
  { header: "階", key: "floor", kind: "int" },
  { header: "間取り", key: "layout", kind: "string" },
  { header: "ステータス", key: "status", kind: "string" },
  { header: "面積(㎡)", key: "squareMeters", kind: "float" },
  { header: "賃料", key: "rent", kind: "int" },
];

// 入居者（Tenant）— 部屋＋入居者シートの入居者側（同じ行に並べる）
export const TENANT_COLS: Col[] = [
  { header: "入居者名", key: "name", kind: "string" },
  { header: "入居者電話", key: "phone", kind: "string" },
  { header: "入居者メール", key: "email", kind: "string" },
  { header: "契約開始", key: "contractStart", kind: "date" },
  { header: "契約終了", key: "contractEnd", kind: "date" },
  { header: "入居日", key: "moveInDate", kind: "date" },
  { header: "職業・勤務先", key: "occupation", kind: "string" },
  { header: "共益費", key: "condoFee", kind: "int" },
  { header: "敷金", key: "depositAmount", kind: "int" },
  { header: "礼金", key: "keyMoney", kind: "int" },
  { header: "更新料", key: "renewalFee", kind: "int" },
  { header: "支払方法", key: "paymentMethod", kind: "string" },
  { header: "保証会社", key: "guarantorCompany", kind: "string" },
  { header: "保証契約番号", key: "guarantorContractNumber", kind: "string" },
];

function toDateStr(d: Date): string {
  // ローカル時刻ではなくUTCベースでYYYY-MM-DD（DBはUTC保存）
  return d.toISOString().slice(0, 10);
}

/** DB値→Excelセル値 */
export function formatCell(v: unknown, kind: ColKind): string | number | "" {
  if (v === null || v === undefined || v === "") return "";
  if (v instanceof Date) return toDateStr(v);
  if (kind === "bool") return v ? "はい" : "いいえ";
  if (kind === "int" || kind === "float") return typeof v === "number" ? v : Number(v);
  if (kind === "date" && typeof v === "string") return v.slice(0, 10);
  return String(v);
}

/** Excelセル値→DB値（空はnull） */
export function parseCell(v: unknown, kind: ColKind): unknown {
  if (v === null || v === undefined || String(v).trim() === "") return null;
  const s = String(v).trim();
  switch (kind) {
    case "bool":
      return s === "はい" || s === "true" || s === "TRUE" || s === "1" || v === true || v === 1;
    case "int": {
      const n = parseInt(s.replace(/[^\d-]/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    }
    case "float": {
      const n = parseFloat(s.replace(/[^\d.-]/g, ""));
      return Number.isFinite(n) ? n : null;
    }
    case "date": {
      const d = new Date(s);
      return isNaN(d.getTime()) ? null : d;
    }
    default:
      return s;
  }
}

/** レコード配列→シート用の行オブジェクト配列（ヘッダーキー） */
export function toRows(records: Record<string, unknown>[], cols: Col[]): Record<string, string | number | "">[] {
  return records.map((r) => {
    const row: Record<string, string | number | ""> = {};
    for (const c of cols) row[c.header] = formatCell(r[c.key], c.kind);
    return row;
  });
}

/** シート行（ヘッダーキー）→ {key:value} の部分データ。空欄・readOnlyは除外。 */
export function fromRow(row: Record<string, unknown>, cols: Col[], includeReadOnly = false): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const c of cols) {
    if (c.readOnly && !includeReadOnly) continue;
    if (!(c.header in row)) continue;
    const parsed = parseCell(row[c.header], c.kind);
    data[c.key] = parsed;
  }
  return data;
}
