import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { AddRoomButton } from "../AddRoomButton";
import { DeleteRoomButton } from "../DeleteRoomButton";
import { unitsLabel } from "@/lib/labels";

export default async function BuildingRoomsPage(props: PageProps<"/buildings/[id]/rooms">) {
  const { id } = await props.params;
  const building = await prisma.building.findUnique({
    where: { id },
    include: {
      rooms: {
        include: { tenant: true, repairs: true },
        orderBy: [{ floor: "asc" }, { roomNumber: "asc" }],
      },
    },
  });
  if (!building) notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="mb-1">
            <Link href={`/buildings/${building.id}`} className="text-sm text-blue-600 hover:underline">
              ← {building.name} の詳細
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">{building.name}｜{unitsLabel(building.type)}</h1>
        </div>
        <AddRoomButton buildingId={building.id} />
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-slate-700">部屋一覧（{building.rooms.length}室）</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">部屋番号</th>
                <th className="px-4 py-3 text-left">階</th>
                <th className="px-4 py-3 text-left">間取り</th>
                <th className="px-4 py-3 text-left">面積</th>
                <th className="px-4 py-3 text-left">賃料</th>
                <th className="px-4 py-3 text-left">ステータス</th>
                <th className="px-4 py-3 text-left">入居者</th>
                <th className="px-4 py-3 text-left">修繕</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {building.rooms.map((room) => (
                <tr key={room.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/rooms/${room.id}`} className="text-blue-600 hover:underline font-medium">
                      {room.roomNumber}号室
                    </Link>
                  </td>
                  <td className="px-4 py-3">{room.floor}F</td>
                  <td className="px-4 py-3">{room.layout}</td>
                  <td className="px-4 py-3 text-slate-500">{room.squareMeters ? `${room.squareMeters}㎡` : "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{room.rent ? `¥${room.rent.toLocaleString()}` : "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={room.status} /></td>
                  <td className="px-4 py-3 text-slate-600">{room.tenant?.name ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-500">{room.repairs.length > 0 ? `${room.repairs.length}件` : "—"}</td>
                  <td className="px-4 py-3">
                    <DeleteRoomButton roomId={room.id} buildingId={building.id} roomNumber={room.roomNumber} />
                  </td>
                </tr>
              ))}
              {building.rooms.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    部屋がありません。「+ 部屋を追加」から登録してください。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
