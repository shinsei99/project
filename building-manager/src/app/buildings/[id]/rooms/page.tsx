import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { AddRoomButton } from "../AddRoomButton";
import { DeleteRoomButton } from "../DeleteRoomButton";
import { unitsLabel } from "@/lib/labels";

// レントロール（Excel）のシートに合わせた表示。カテゴリごとに列構成を変える。
const yen = (n?: number | null) => (n == null ? "—" : `¥${n.toLocaleString()}`);

function fmtDate(d?: Date | null): string {
  if (!d) return "—";
  const y = d.getFullYear();
  if (y <= 2000 || y >= 2099) return "—"; // 取り込み時のプレースホルダ日付は非表示
  return `${y}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

export default async function BuildingRoomsPage(props: PageProps<"/buildings/[id]/rooms">) {
  const { id } = await props.params;
  const building = await prisma.building.findUnique({
    where: { id },
    include: {
      rooms: {
        include: { tenant: true },
        orderBy: [{ floor: "asc" }, { roomNumber: "asc" }],
      },
    },
  });
  if (!building) notFound();

  type Row = (typeof building.rooms)[number];
  const total = (r: Row) =>
    r.tenant
      ? (r.rent ?? 0) + (r.tenant.condoFee ?? 0) + (r.tenant.waterFee ?? 0)
      : r.rent ?? null;

  // カテゴリ別の列定義（Excelレントロールの見出しに準拠）
  type Col = { label: string; cell: (r: Row) => React.ReactNode; num?: boolean };
  const contractor: Col = { label: "契約者", cell: (r) => r.tenant?.name ?? "—" };
  const kind: Col = { label: "区分", cell: (r) => r.tenant?.tenantKind ?? "—" };
  const status: Col = { label: "現況", cell: (r) => <StatusBadge status={r.status} /> };
  const rent = (label: string): Col => ({ label, cell: (r) => yen(r.rent), num: true });
  const kyoueki: Col = { label: "共益費", cell: (r) => yen(r.tenant?.condoFee), num: true };
  const water: Col = { label: "水道代", cell: (r) => yen(r.tenant?.waterFee), num: true };
  const goukei: Col = { label: "合計", cell: (r) => yen(total(r)), num: true };
  const deposit: Col = { label: "保証金", cell: (r) => yen(r.tenant?.depositAmount), num: true };
  const contractDate: Col = { label: "契約日", cell: (r) => fmtDate(r.tenant?.contractStart) };
  const note: Col = { label: "備考", cell: (r) => r.note ?? "—" };

  const colsByType: Record<string, Col[]> = {
    マンション: [status, contractor, kind, rent("家賃"), kyoueki, water, goukei, deposit, contractDate, note],
    ビル: [status, contractor, rent("家賃"), kyoueki, goukei, note],
    駐車場: [status, contractor, kind, rent("賃料"), deposit, contractDate, note],
    その他: [status, contractor, rent("賃料"), note],
  };
  const cols = colsByType[building.type] ?? colsByType["その他"];

  const isParking = building.type === "駐車場";
  const numberLabel = isParking ? "区画No" : "号室";
  const numberSuffix = isParking ? "" : "号室";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="mb-1">
            <Link href={`/buildings/${building.id}`} className="text-sm text-blue-600 hover:underline">
              ← {building.name} の詳細
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">
            {building.name}｜{unitsLabel(building.type)}
          </h1>
        </div>
        <AddRoomButton buildingId={building.id} />
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-slate-700">
            レントロール（{building.rooms.length}
            {isParking ? "区画" : "室"}）
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm whitespace-nowrap">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">{numberLabel}</th>
                {cols.map((c) => (
                  <th key={c.label} className={`px-4 py-3 ${c.num ? "text-right" : "text-left"}`}>
                    {c.label}
                  </th>
                ))}
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {building.rooms.map((room) => (
                <tr key={room.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/rooms/${room.id}`} className="text-blue-600 hover:underline font-medium">
                      {room.roomNumber}
                      {numberSuffix}
                    </Link>
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c.label}
                      className={`px-4 py-3 ${c.num ? "text-right text-slate-600 tabular-nums" : "text-slate-600"}`}
                    >
                      {c.cell(room)}
                    </td>
                  ))}
                  <td className="px-4 py-3">
                    <DeleteRoomButton roomId={room.id} buildingId={building.id} roomNumber={room.roomNumber} />
                  </td>
                </tr>
              ))}
              {building.rooms.length === 0 && (
                <tr>
                  <td colSpan={cols.length + 2} className="px-4 py-12 text-center text-slate-400">
                    {isParking ? "区画" : "部屋"}がありません。ダッシュボードの「🔄 今すぐ同期」または「+ 追加」から登録してください。
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
