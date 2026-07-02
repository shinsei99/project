export type RoomStatus = "入居中" | "募集中" | "リフォーム中";
export type RepairCategory = "水回り" | "エアコン" | "内装" | "電気" | "設備" | "その他";
export type InvoiceStatus = "未保管" | "保管済";
export type BuildingType = "マンション" | "ビル" | "駐車場" | "その他";
export type PaymentMethod = "銀行振込" | "口座振替" | "保証会社送金" | "その他";

export const ROOM_STATUSES: RoomStatus[] = ["入居中", "募集中", "リフォーム中"];
export const REPAIR_CATEGORIES: RepairCategory[] = ["水回り", "エアコン", "内装", "電気", "設備", "その他"];
export const BUILDING_TYPES: BuildingType[] = ["マンション", "ビル", "駐車場", "その他"];

export type HandlingType = "管理" | "仲介";
export const HANDLING_TYPES: HandlingType[] = ["管理", "仲介"];
export const PAYMENT_METHODS: PaymentMethod[] = ["銀行振込", "口座振替", "保証会社送金", "その他"];
