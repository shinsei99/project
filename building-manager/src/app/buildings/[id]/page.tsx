import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { HandlingBadge } from "@/components/HandlingBadge";
import { BuildingInfoPanel } from "@/components/BuildingInfoPanel";
import { unitsLabel } from "@/lib/labels";

export default async function BuildingDetailPage(props: PageProps<"/buildings/[id]">) {
  const { id } = await props.params;
  const building = await prisma.building.findUnique({
    where: { id },
    include: {
      owner: { include: { _count: { select: { buildings: true } } } },
      _count: { select: { rooms: true } },
    },
  });
  if (!building) notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="mb-1">
            <Link href={`/?type=${building.type}`} className="text-sm text-blue-600 hover:underline">
              ← {building.type}一覧
            </Link>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-slate-800">{building.name}</h1>
            <HandlingBadge handling={building.handling} />
          </div>
          {building.address && <p className="text-sm text-slate-400 mt-1">{building.address}</p>}
        </div>
      </div>

      {/* 部屋一覧/契約者一覧への導線 */}
      <Link
        href={`/buildings/${building.id}/rooms`}
        className="flex items-center justify-between bg-slate-800 text-white rounded-xl px-6 py-4 shadow hover:bg-slate-700 transition-colors"
      >
        <div>
          <p className="font-semibold">🚪 {unitsLabel(building.type)}・管理</p>
          <p className="text-xs text-slate-300 mt-0.5">
            {building.type === "駐車場" ? "区画・契約者・修繕・請求書の管理はこちら" : "部屋・入居者・修繕・請求書の管理はこちら"}
          </p>
        </div>
        <span className="text-sm">{building._count.rooms}{building.type === "駐車場" ? "区画" : "室"} →</span>
      </Link>

      <BuildingInfoPanel buildingType={building.type} values={building} />

      {/* オーナー情報（取り込みデータの表示のみ） */}
      <section className="bg-white rounded-xl shadow p-5 space-y-3">
        <h2 className="font-semibold text-slate-700 border-b pb-2">オーナー</h2>
        {building.owner ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {building.owner.company && (
              <>
                <dt className="text-slate-500">法人名</dt>
                <dd className="font-medium">{building.owner.company}</dd>
              </>
            )}
            <dt className="text-slate-500">氏名</dt>
            <dd className="font-medium">{building.owner.name}</dd>
            {building.owner.address && (
              <>
                <dt className="text-slate-500">住所</dt>
                <dd>{building.owner.address}</dd>
              </>
            )}
            {building.owner.phone && (
              <>
                <dt className="text-slate-500">TEL</dt>
                <dd>{building.owner.phone}</dd>
              </>
            )}
            {building.owner.email && (
              <>
                <dt className="text-slate-500">メール</dt>
                <dd>{building.owner.email}</dd>
              </>
            )}
            {building.owner.note && (
              <>
                <dt className="text-slate-500">備考</dt>
                <dd>{building.owner.note}</dd>
              </>
            )}
            <dt className="text-slate-500">所有物件数</dt>
            <dd>{building.owner._count.buildings}件</dd>
          </dl>
        ) : (
          <p className="text-sm text-slate-400">オーナー情報なし</p>
        )}
      </section>
    </div>
  );
}
