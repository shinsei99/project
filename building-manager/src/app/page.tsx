import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { AddBuildingButton } from "@/components/AddBuildingButton";
import { BUILDING_TYPES } from "@/types";

export default async function DashboardPage(props: PageProps<"/">) {
  const { type } = (await props.searchParams) as { type?: string };
  const activeType = type && BUILDING_TYPES.includes(type as "マンション" | "ビル") ? type : "マンション";

  const buildings = await prisma.building.findMany({
    where: { type: activeType },
    include: {
      rooms: {
        include: { tenant: true, repairs: { include: { invoice: true } } },
        orderBy: [{ floor: "asc" }, { roomNumber: "asc" }],
      },
    },
    orderBy: { createdAt: "asc" },
  });

  const allRooms = buildings.flatMap((b) => b.rooms);
  const total = allRooms.length;
  const occupied = allRooms.filter((r) => r.status === "入居中").length;
  const vacant = allRooms.filter((r) => r.status === "空室").length;
  const renovating = allRooms.filter((r) => r.status === "リフォーム中").length;
  const uninvoiced = allRooms
    .flatMap((r) => r.repairs)
    .filter((rep) => rep.invoice?.status === "未保管").length;

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
              {t === "マンション" ? "🏠 マンション" : "🏢 ビル"}
            </Link>
          ))}
        </div>
        <AddBuildingButton type={activeType} />
      </div>

      {/* サマリーカード */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          { label: "総部屋数", value: total, color: "bg-slate-700" },
          { label: "入居中", value: occupied, color: "bg-green-600" },
          { label: "空室", value: vacant, color: "bg-slate-400" },
          { label: "リフォーム中", value: renovating, color: "bg-yellow-500" },
          { label: "請求書未保管", value: uninvoiced, color: "bg-red-500" },
        ].map((card) => (
          <div key={card.label} className={`${card.color} text-white rounded-xl p-4 shadow`}>
            <p className="text-3xl font-bold">{card.value}</p>
            <p className="text-sm mt-1 opacity-90">{card.label}</p>
          </div>
        ))}
      </div>

      {/* 物件ごとのカード */}
      {buildings.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-12 text-center text-slate-400">
          <p className="text-lg">{activeType}がまだ登録されていません</p>
          <p className="text-sm mt-2">「+ {activeType}を追加」から登録してください</p>
        </div>
      ) : (
        buildings.map((building) => (
          <div key={building.id} className="bg-white rounded-xl shadow overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b bg-slate-50">
              <div>
                <h2 className="font-bold text-slate-800">{building.name}</h2>
                {building.address && (
                  <p className="text-xs text-slate-400 mt-0.5">{building.address}</p>
                )}
              </div>
              <Link
                href={`/buildings/${building.id}`}
                className="text-sm text-blue-600 hover:underline"
              >
                詳細・部屋管理 →
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-slate-500 text-xs uppercase tracking-wide">
                  <tr>
                    <th className="px-4 py-2 text-left">部屋</th>
                    <th className="px-4 py-2 text-left">間取り</th>
                    <th className="px-4 py-2 text-left">ステータス</th>
                    <th className="px-4 py-2 text-left">入居者</th>
                    <th className="px-4 py-2 text-left">賃料</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {building.rooms.map((room) => (
                    <tr key={room.id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">
                        <Link
                          href={`/rooms/${room.id}`}
                          className="text-blue-600 hover:underline font-medium"
                        >
                          {room.roomNumber}号室
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-slate-600">{room.layout}</td>
                      <td className="px-4 py-2">
                        <StatusBadge status={room.status} />
                      </td>
                      <td className="px-4 py-2 text-slate-600">{room.tenant?.name ?? "—"}</td>
                      <td className="px-4 py-2 text-slate-600">
                        {room.rent ? `¥${room.rent.toLocaleString()}` : "—"}
                      </td>
                    </tr>
                  ))}
                  {building.rooms.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-400 text-xs">
                        部屋がありません
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
