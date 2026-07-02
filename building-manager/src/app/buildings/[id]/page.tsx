import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { EditBuildingButton } from "./EditBuildingButton";
import { EditBuildingInfoButton } from "./EditBuildingInfoButton";
import { AiBuildingExtractButton } from "./AiBuildingExtractButton";
import { DeleteBuildingButton } from "./DeleteBuildingButton";
import { HandlingSelect } from "./HandlingSelect";
import { OwnerCard } from "./OwnerCard";
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

  const allOwners = await prisma.owner.findMany({
    select: { id: true, company: true, name: true },
    orderBy: { createdAt: "asc" },
  });

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
            <HandlingSelect buildingId={building.id} value={building.handling} />
          </div>
          {building.address && <p className="text-sm text-slate-400 mt-1">{building.address}</p>}
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <AiBuildingExtractButton buildingId={building.id} buildingType={building.type} />
          <EditBuildingInfoButton buildingId={building.id} buildingType={building.type} values={building} />
          <EditBuildingButton buildingId={building.id} name={building.name} type={building.type} address={building.address} />
          <DeleteBuildingButton buildingId={building.id} buildingName={building.name} />
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

      <OwnerCard
        buildingId={building.id}
        allOwners={allOwners}
        owner={
          building.owner
            ? {
                id: building.owner.id,
                company: building.owner.company,
                name: building.owner.name,
                address: building.owner.address,
                phone: building.owner.phone,
                fax: building.owner.fax,
                email: building.owner.email,
                note: building.owner.note,
                buildingCount: building.owner._count.buildings,
              }
            : null
        }
      />
    </div>
  );
}
