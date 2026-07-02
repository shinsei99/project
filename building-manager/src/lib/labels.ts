// 建物タイプ別の表記ゆれを一元化する。
// 駐車場は「部屋」ではなく「区画／契約者」の概念なので表記を変える。

/** 詳細ページのラベル（駐車場のみ「駐車場詳細」） */
export function detailLabel(type: string): string {
  return type === "駐車場" ? "駐車場詳細" : "建物詳細";
}

/** 部屋一覧ページのラベル（駐車場のみ「契約者一覧」） */
export function unitsLabel(type: string): string {
  return type === "駐車場" ? "契約者一覧" : "部屋一覧";
}
