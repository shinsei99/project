// 建物レベル項目の単一情報源。
// Prisma schema（Buildingモデル）・編集フォーム・AI抽出プレビュー・詳細表示を
// すべてこの定義から駆動する。

export type BuildingFieldType = "text" | "int" | "float" | "bool";
export type BuildingScope = "common" | "マンション" | "ビル" | "駐車場" | "その他";

export interface BuildingFieldDef {
  key: string;
  label: string;
  type: BuildingFieldType;
  scope: BuildingScope;
  unit?: string;
  placeholder?: string;
  /** 手入力が基本でAI抽出対象外にしたい項目（オーナー連絡先など） */
  manualOnly?: boolean;
}

export const BUILDING_FIELDS: BuildingFieldDef[] = [
  // 共通
  { key: "access", label: "交通・最寄駅", type: "text", scope: "common", placeholder: "〇〇線 〇〇駅 徒歩5分" },
  { key: "structure", label: "構造・規模", type: "text", scope: "common", placeholder: "鉄骨造 9階建" },
  { key: "builtDate", label: "築年月", type: "text", scope: "common", placeholder: "1987-03" },
  { key: "landArea", label: "敷地面積", type: "float", scope: "common", unit: "㎡" },
  { key: "totalFloorArea", label: "延床面積", type: "float", scope: "common", unit: "㎡" },
  { key: "parkingCount", label: "駐車場台数", type: "int", scope: "common", unit: "台" },
  { key: "managementCompany", label: "管理会社", type: "text", scope: "common" },
  { key: "facilities", label: "共用設備", type: "text", scope: "common", placeholder: "メールボックス, EV, オートロック..." },
  { key: "note", label: "備考", type: "text", scope: "common" },

  // マンション専用
  { key: "totalUnits", label: "総戸数", type: "int", scope: "マンション", unit: "戸" },
  { key: "rentalUnits", label: "賃貸戸数", type: "int", scope: "マンション", unit: "戸" },
  { key: "managementForm", label: "管理形態", type: "text", scope: "マンション", placeholder: "全部委託/一部委託/自主管理" },
  { key: "managerType", label: "管理員", type: "text", scope: "マンション", placeholder: "常駐/日勤/巡回/なし" },
  { key: "managementFee", label: "管理費(月額)", type: "int", scope: "マンション", unit: "円" },
  { key: "repairReserve", label: "修繕積立金(月額)", type: "int", scope: "マンション", unit: "円" },
  { key: "autoLock", label: "オートロック", type: "bool", scope: "マンション" },
  { key: "deliveryBox", label: "宅配ボックス", type: "bool", scope: "マンション" },
  { key: "hasElevator", label: "エレベーター", type: "bool", scope: "マンション" },

  // ビル専用
  { key: "rentableArea", label: "貸室総面積", type: "float", scope: "ビル", unit: "㎡" },
  { key: "standardFloorArea", label: "基準階面積", type: "float", scope: "ビル", unit: "㎡" },
  { key: "zoning", label: "用途地域", type: "text", scope: "ビル", placeholder: "商業地域 など" },
  { key: "elevatorCount", label: "エレベーター基数", type: "int", scope: "ビル", unit: "基" },
  { key: "hvacType", label: "空調方式", type: "text", scope: "ビル", placeholder: "セントラル/個別" },
  { key: "rentPerTsubo", label: "想定賃料(坪単価)", type: "int", scope: "ビル", unit: "円" },
  { key: "commonFeePerTsubo", label: "共益費(坪単価)", type: "int", scope: "ビル", unit: "円" },
  { key: "securityCompany", label: "警備会社", type: "text", scope: "ビル" },
  { key: "fireInspector", label: "消防点検業者", type: "text", scope: "ビル" },

  // 駐車場専用
  { key: "parkingType", label: "駐車場種別", type: "text", scope: "駐車場", placeholder: "平面/自走式/機械式" },
  { key: "totalSpaces", label: "総区画数", type: "int", scope: "駐車場", unit: "区画" },
  { key: "vacantSpaces", label: "空き区画数", type: "int", scope: "駐車場", unit: "区画" },
  { key: "monthlyRate", label: "月極賃料", type: "int", scope: "駐車場", unit: "円" },
  { key: "carSize", label: "車室寸法・制限", type: "text", scope: "駐車場", placeholder: "全長5.0m/全高1.55m 等" },
  { key: "hasRoof", label: "屋根あり", type: "bool", scope: "駐車場" },
];

export const BUILDING_FIELD_MAP: Record<string, BuildingFieldDef> = Object.fromEntries(
  BUILDING_FIELDS.map((f) => [f.key, f]),
);

/** 種別（マンション/ビル）に応じて表示すべき項目一覧を返す。共通→種別専用の順。 */
export function fieldsForType(type: string): BuildingFieldDef[] {
  return BUILDING_FIELDS.filter((f) => f.scope === "common" || f.scope === type);
}

/** フォーム/AIの生値を Prisma 用に型変換する（空はnull）。 */
export function coerceBuildingValue(def: BuildingFieldDef, raw: unknown): unknown {
  if (raw === null || raw === undefined || raw === "") return null;
  switch (def.type) {
    case "int": {
      const n = parseInt(String(raw).replace(/[^\d-]/g, ""), 10);
      return Number.isFinite(n) ? n : null;
    }
    case "float": {
      const n = parseFloat(String(raw).replace(/[^\d.-]/g, ""));
      return Number.isFinite(n) ? n : null;
    }
    case "bool":
      return raw === true || raw === "true" || raw === "はい" || raw === 1 || raw === "1";
    default:
      return String(raw);
  }
}

/** 表示用に値を整形（bool→はい/いいえ、単位付与）。null/未設定は null を返す。 */
export function formatBuildingValue(def: BuildingFieldDef, value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (def.type === "bool") return value ? "あり" : "なし";
  const base = def.type === "int" || def.type === "float" ? Number(value).toLocaleString() : String(value);
  return def.unit ? `${base}${def.unit}` : base;
}
