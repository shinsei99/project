export type RoomStatus = "入居中" | "空室" | "リフォーム中";
export type RepairCategory = "水回り" | "エアコン" | "内装" | "電気" | "設備" | "その他";
export type InvoiceStatus = "未保管" | "保管済";
export type BuildingType = "マンション" | "ビル";
export type PaymentMethod = "銀行振込" | "口座振替" | "保証会社送金" | "その他";

export const ROOM_STATUSES: RoomStatus[] = ["入居中", "空室", "リフォーム中"];
export const REPAIR_CATEGORIES: RepairCategory[] = ["水回り", "エアコン", "内装", "電気", "設備", "その他"];
export const BUILDING_TYPES: BuildingType[] = ["マンション", "ビル"];
export const PAYMENT_METHODS: PaymentMethod[] = ["銀行振込", "口座振替", "保証会社送金", "その他"];
