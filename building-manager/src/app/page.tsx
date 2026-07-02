import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { AddBuildingButton } from "@/components/AddBuildingButton";
import { HandlingBadge } from "@/components/HandlingBadge";
import { detailLabel, unitsLabel } from "@/lib/labels";
import { BUILDING_TYPES, BuildingType } from "@/types";

const TYPE_ICON: Record<BuildingType, string> = {
  マンション: "🏠",
  ビル: "🏢",
  駐車場: "🅿️",
  その他: "📦",
};

// 部屋群からステータス別件数を集計（全体・建物ごと共通で使う）
function roomStats(rooms: { status: string }[]) {
  return {
    total: rooms.length,
    occupied: rooms.filter((r) => r.status === "入居中").length,
    vacant: rooms.filter((r) => r.status === "募集中").length,
    renovating: rooms.filter((r) => r.status === "リフォーム中").length,
  };
}

// 4指標の表示定義（ラベル・色）
const STAT_DEFS = [
  { key: "total", label: "総部屋数", color: "bg-slate-700", dot: "bg-slate-400" },
  { key: "occupied", label: "入居中", color: "bg-green-600", dot: "bg-green-500" },
  { key: "vacant", label: "募集中", color: "bg-blue-600", dot: "bg-blue-500" },
  { key: "renovating", label: "リフォーム中", color: "bg-yellow-500", dot: "bg-yellow-500" },
] as const;

export default async function DashboardPage(props: PageProps<"/">) {
  const { type } = (await props.searchParams) as { type?: string };
  const activeType = type && BUILDING_TYPES.includes(type as BuildingType) ? type : "マンション";

  const buildings = await prisma.building.findMany({
    where: { type: activeType },
    include: {
      rooms: {
        select: { id: true, roomNumber: true, floor: true, layout: true, rent: true, status: true },
        orderBy: [{ floor: "asc" }, { roomNumber: "asc" }],
      },
    },
    orderBy: { createdAt: "asc" },
  });

  return (
    <div className="space-y-6">
      {/* タブ切り替え */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-slate-100 p-1 rounded-xl">
          {BUILDING_TYPES.map((t) => (
            <Link
              key={t}
              href={`/?type=${t}`}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeType === t
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {TYPE_ICON[t]} {t}
            </Link>
          ))}
        </div>
        <AddBuildingButton type={activeType} />
      </div>

      {/* 物件ごとのカード */}
      {buildings.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-12 text-center text-slate-400">
          <p className="text-lg">{activeType}がまだ登録されていません</p>
          <p className="text-sm mt-2">「+ {activeType}を追加」から登録してください</p>
        </div>
      ) : (
        buildings.map((building) => {
          const stats = roomStats(building.rooms);
          const vacantRooms = building.rooms.filter((r) => r.status === "募集中");
          return (
          <div key={building.id} className="bg-white rounded-xl shadow overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b bg-slate-50 gap-4 flex-wrap">
              <div>
                <h2 className="font-bold text-slate-800">{building.name}</h2>
                {building.address && (
                  <p className="text-xs text-slate-400 mt-0.5">{building.address}</p>
                )}
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                {/* 管理/仲介 区分（総部屋数の左に表示） */}
                <HandlingBadge handling={building.handling} />
                {/* 建物ごとの4指標（名前の横に表示） */}
                <div className="flex items-center gap-2">
                  {STAT_DEFS.map((s) => (
                    <div
                      key={s.key}
                      className={`${s.color} text-white rounded-lg px-3 py-1.5 text-center min-w-[64px] shadow-sm`}
                      title={s.label}
                    >
                      <p className="text-lg font-bold leading-none">{stats[s.key]}</p>
                      <p className="text-[10px] mt-1 opacity-90 leading-none">{s.label}</p>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-3 whitespace-nowrap">
                  <Link href={`/buildings/${building.id}`} className="text-sm text-blue-600 hover:underline">
                    {detailLabel(building.type)} →
                  </Link>
                  <Link href={`/buildings/${building.id}/rooms`} className="text-sm text-blue-600 hover:underline">
                    {unitsLabel(building.type)} →
                  </Link>
                </div>
              </div>
            </div>

            {/* 募集中の部屋のみ表示 */}
            <div className="px-6 py-4">
              {vacantRooms.length === 0 ? (
                <p className="text-sm text-slate-400">募集中の部屋はありません（満室）</p>
              ) : (
                <>
                  <p className="text-xs font-semibold text-blue-600 mb-2">🔵 募集中の部屋（{vacantRooms.length}室）</p>
                  <div className="flex flex-wrap gap-2">
                    {vacantRooms.map((room) => (
                      <Link
                        key={room.id}
                        href={`/rooms/${room.id}`}
                        className="border border-blue-200 bg-blue-50 rounded-lg px-3 py-2 hover:bg-blue-100 transition-colors"
                      >
                        <span className="font-medium text-slate-800 text-sm">{room.roomNumber}号室</span>
                        <span className="text-xs text-slate-500 ml-2">{room.floor}F・{room.layout}</span>
                        {room.rent != null && (
                          <span className="text-xs font-medium text-slate-700 ml-2">¥{room.rent.toLocaleString()}</span>
                        )}
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
          );
        })
      )}
    </div>
  );
}
