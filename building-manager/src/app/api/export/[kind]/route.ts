import * as XLSX from "xlsx";
import { prisma } from "@/lib/prisma";
import { BUILDING_COLS, OWNER_COLS, ROOM_COLS, TENANT_COLS, toRows } from "@/lib/dataTables";

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function xlsxResponse(rows: Record<string, unknown>[], sheetName: string, filename: string): Response {
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  const buf: Buffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });
  return new Response(new Uint8Array(buf), {
    headers: {
      "Content-Type": XLSX_MIME,
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}

// エクスポートには暗証番号 4242 が必要（全データ・オーナー個人情報を含むため）
const EXPORT_PIN = "4242";

export async function GET(req: Request, props: { params: Promise<{ kind: string }> }) {
  const { kind } = await props.params;

  const pin = new URL(req.url).searchParams.get("pin");
  if (pin !== EXPORT_PIN) {
    return new Response(JSON.stringify({ error: "暗証番号が違います" }), {
      status: 403,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (kind === "all") {
    // 全テーブルの完全バックアップ（JSON）
    const [buildings, rooms, tenants, securityInfos, repairHistories, invoices, owners] = await Promise.all([
      prisma.building.findMany(),
      prisma.room.findMany(),
      prisma.tenant.findMany(),
      prisma.securityInfo.findMany(),
      prisma.repairHistory.findMany(),
      prisma.invoice.findMany(),
      prisma.owner.findMany(),
    ]);
    const payload = {
      _meta: { app: "building-manager", version: 1 },
      owners, buildings, rooms, tenants, securityInfos, repairHistories, invoices,
    };
    return new Response(JSON.stringify(payload, null, 2), {
      headers: {
        "Content-Type": "application/json",
        "Content-Disposition": `attachment; filename="building-manager-backup.json"`,
      },
    });
  }

  if (kind === "buildings") {
    const buildings = await prisma.building.findMany({ orderBy: { createdAt: "asc" } });
    return xlsxResponse(toRows(buildings as unknown as Record<string, unknown>[], BUILDING_COLS), "建物", "buildings.xlsx");
  }

  if (kind === "owners") {
    const owners = await prisma.owner.findMany({ orderBy: { createdAt: "asc" } });
    return xlsxResponse(toRows(owners as unknown as Record<string, unknown>[], OWNER_COLS), "オーナー", "owners.xlsx");
  }

  if (kind === "rooms") {
    const rooms = await prisma.room.findMany({
      include: { building: true, tenant: true },
      orderBy: [{ building: { name: "asc" } }, { floor: "asc" }, { roomNumber: "asc" }],
    });
    const merged = rooms.map((r) => ({
      ...r,
      buildingName: r.building?.name ?? "",
      // 入居者フィールドを同じ行に展開（id等は含めない＝部屋idを維持）
      ...(r.tenant
        ? Object.fromEntries(TENANT_COLS.map((c) => [c.key, (r.tenant as Record<string, unknown>)[c.key]]))
        : {}),
    }));
    return xlsxResponse(
      toRows(merged as unknown as Record<string, unknown>[], [...ROOM_COLS, ...TENANT_COLS]),
      "部屋と入居者",
      "rooms.xlsx",
    );
  }

  return new Response(JSON.stringify({ error: "unknown export kind" }), { status: 400 });
}
