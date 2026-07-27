import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { AddRoomButton } from "../AddRoomButton";
import { DeleteRoomButton } from "../DeleteRoomButton";
import { unitsLabel } from "@/lib/labels";

// レントロール（Excel）のシートに合わせた表示。カテゴリ・セクション（居室／車庫）ごとに列を変える。
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
    r.tenant ? (r.rent ?? 0) + (r.tenant.condoFee ?? 0) + (r.tenant.waterFee ?? 0) : r.rent ?? null;

  // 列定義部品
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

  // 居室セクションの列（建物カテゴリで可変）
  const residentialCols: Record<string, Col[]> = {
    マンション: [status, contractor, kind, rent("家賃"), kyoueki, water, goukei, deposit, contractDate, note],
    ビル: [status, contractor, rent("家賃"), kyoueki, goukei, note],
    駐車場: [status, contractor, kind, rent("賃料"), deposit, contractDate, note],
    その他: [status, contractor, rent("賃料"), note],
  };
  // 車庫セクションの列（駐車場と同じ）
  const garageCols: Col[] = [status, contractor, kind, rent("賃料"), deposit, contractDate, note];

  const isParking = building.type === "駐車場";

  // セクション分け：居室（section=null）→ 各車庫セクション
  const residential = building.rooms.filter((r) => (r.unitType ?? "居室") === "居室");
  const garageSections = new Map<string, Row[]>();
  for (const r of building.rooms) {
    if ((r.unitType ?? "居室") !== "居室") {
      const key = r.section ?? "車庫";
      (garageSections.get(key) ?? garageSections.set(key, []).get(key)!).push(r);
    }
  }

  // 表示番号：車庫は "セクション名-番号" で保存しているのでプレフィックスを外す
  const displayNo = (r: Row) => (r.section && r.roomNumber.startsWith(r.section + "-") ? r.roomNumber.slice(r.section.length + 1) : r.roomNumber);

  type Section = { title: string; numberLabel: string; suffix: string; cols: Col[]; rows: Row[] };
  const sections: Section[] = [];
  sections.push({
    title: isParking ? "区画" : "居室",
    numberLabel: isParking ? "区画No" : "号室",
    suffix: isParking ? "" : "号室",
    cols: residentialCols[building.type] ?? residentialCols["その他"],
    rows: residential,
  });
  for (const [name, rows] of garageSections) {
    sections.push({ title: name, numberLabel: "番号", suffix: "", cols: garageCols, rows });
  }

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
          <p className="text-xs text-slate-400 mt-1">
            居室 {residential.length}
            {isParking ? "区画" : "室"}
            {garageSections.size > 0 &&
              " ／ " +
                [...garageSections].map(([n, r]) => `${n} ${r.length}台`).join(" ／ ")}
          </p>
        </div>
        <AddRoomButton buildingId={building.id} />
      </div>

      {sections.map((sec) => (
        <div key={sec.title} className="bg-white rounded-xl shadow overflow-hidden">
          <div className="px-6 py-4 border-b flex items-center gap-2">
            <h2 className="font-semibold text-slate-700">
              {sec.title === "居室" || sec.title === "区画" ? "" : "🚗 "}
              {sec.title}
            </h2>
            <span className="text-xs text-slate-400">（{sec.rows.length}）</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">{sec.numberLabel}</th>
                  {sec.cols.map((c) => (
                    <th key={c.label} className={`px-4 py-3 ${c.num ? "text-right" : "text-left"}`}>
                      {c.label}
                    </th>
                  ))}
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sec.rows.map((room) => (
                  <tr key={room.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link href={`/rooms/${room.id}`} className="text-blue-600 hover:underline font-medium">
                        {displayNo(room)}
                        {sec.suffix}
                      </Link>
                    </td>
                    {sec.cols.map((c) => (
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
                {sec.rows.length === 0 && (
                  <tr>
                    <td colSpan={sec.cols.length + 2} className="px-4 py-12 text-center text-slate-400">
                      データがありません。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
