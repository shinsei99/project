import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { ROOM_STATUSES } from "@/types";

export default async function RoomsPage(props: PageProps<"/rooms">) {
  const { status } = await props.searchParams as { status?: string };

  const rooms = await prisma.room.findMany({
    where: status ? { status } : undefined,
    include: { tenant: true },
    orderBy: [{ floor: "asc" }, { roomNumber: "asc" }],
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">部屋一覧</h1>
      </div>

      {/* フィルター */}
      <div className="flex gap-2 flex-wrap">
        <Link
          href="/rooms"
          className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${!status ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"}`}
        >
          すべて
        </Link>
        {ROOM_STATUSES.map((s) => (
          <Link
            key={s}
            href={`/rooms?status=${s}`}
            className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${status === s ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"}`}
          >
            {s}
          </Link>
        ))}
      </div>

      {/* テーブル */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">部屋番号</th>
                <th className="px-4 py-3 text-left">階</th>
                <th className="px-4 py-3 text-left">間取り</th>
                <th className="px-4 py-3 text-left">面積</th>
                <th className="px-4 py-3 text-left">賃料</th>
                <th className="px-4 py-3 text-left">ステータス</th>
                <th className="px-4 py-3 text-left">入居者</th>
                <th className="px-4 py-3 text-left">契約終了</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rooms.map((room) => (
                <tr key={room.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-semibold">{room.roomNumber}</td>
                  <td className="px-4 py-3">{room.floor}F</td>
                  <td className="px-4 py-3">{room.layout}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {room.squareMeters ? `${room.squareMeters}㎡` : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {room.rent ? `¥${room.rent.toLocaleString()}` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={room.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{room.tenant?.name ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {room.tenant
                      ? new Date(room.tenant.contractEnd).toLocaleDateString("ja-JP")
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/rooms/${room.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      詳細 →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rooms.length === 0 && (
            <p className="text-center py-12 text-slate-400">該当する部屋がありません</p>
          )}
        </div>
      </div>
    </div>
  );
}
