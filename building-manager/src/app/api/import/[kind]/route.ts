import * as XLSX from "xlsx";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import { BUILDING_COLS, OWNER_COLS, ROOM_COLS, TENANT_COLS, fromRow } from "@/lib/dataTables";

function readSheet(buf: Buffer): Record<string, unknown>[] {
  const wb = XLSX.read(buf, { type: "buffer" });
  const ws = wb.Sheets[wb.SheetNames[0]];
  if (!ws) return [];
  return XLSX.utils.sheet_to_json(ws, { defval: "" }) as Record<string, unknown>[];
}

const str = (v: unknown) => (v == null ? "" : String(v));

// ---- Building ----
async function importBuildings(rows: Record<string, unknown>[]) {
  const validOwnerIds = new Set((await prisma.owner.findMany({ select: { id: true } })).map((o) => o.id));
  let created = 0, updated = 0, skipped = 0;
  for (const row of rows) {
    const data = fromRow(row, BUILDING_COLS);
    const id = str(data.id) || null;
    delete data.id;
    // FK安全: 存在しないオーナーIDは無視
    if (data.ownerId && !validOwnerIds.has(str(data.ownerId))) data.ownerId = null;
    // 必須欠落はスキップ/除外
    if (!data.name || !data.type) {
      if (!id) { skipped++; continue; }
      if (!data.name) delete data.name;
      if (!data.type) delete data.type;
    }
    if (id) {
      const exists = await prisma.building.findUnique({ where: { id }, select: { id: true } });
      if (exists) { await prisma.building.update({ where: { id }, data }); updated++; }
      else if (data.name && data.type) { await prisma.building.create({ data: { id, ...data } as never }); created++; }
      else skipped++;
    } else if (data.name && data.type) {
      await prisma.building.create({ data: data as never }); created++;
    } else skipped++;
  }
  return { created, updated, skipped };
}

// ---- Owner ----
async function importOwners(rows: Record<string, unknown>[]) {
  let created = 0, updated = 0, skipped = 0;
  for (const row of rows) {
    const data = fromRow(row, OWNER_COLS);
    const id = str(data.id) || null;
    delete data.id;
    if (!data.name) {
      if (id) delete data.name; else { skipped++; continue; }
    }
    if (id) {
      const exists = await prisma.owner.findUnique({ where: { id }, select: { id: true } });
      if (exists) { await prisma.owner.update({ where: { id }, data }); updated++; }
      else if (data.name) { await prisma.owner.create({ data: { id, ...data } as never }); created++; }
      else skipped++;
    } else if (data.name) {
      await prisma.owner.create({ data: data as never }); created++;
    } else skipped++;
  }
  return { created, updated, skipped };
}

// ---- Room + Tenant（1行に部屋＋入居者） ----
async function importRooms(rows: Record<string, unknown>[]) {
  const validBuildingIds = new Set((await prisma.building.findMany({ select: { id: true } })).map((b) => b.id));
  let created = 0, updated = 0, skipped = 0, tenants = 0;
  for (const row of rows) {
    const roomData = fromRow(row, ROOM_COLS);
    const roomId = str(roomData.id) || null;
    delete roomData.id;
    const buildingId = str(roomData.buildingId);
    const roomNumber = str(roomData.roomNumber);
    if (!validBuildingIds.has(buildingId) || !roomNumber) { skipped++; continue; }
    if (roomData.floor == null) roomData.floor = 1;
    if (!roomData.layout) roomData.layout = "—";
    if (!roomData.status) roomData.status = "募集中";

    let room;
    const existing = roomId
      ? await prisma.room.findUnique({ where: { id: roomId }, select: { id: true } })
      : await prisma.room.findUnique({ where: { buildingId_roomNumber: { buildingId, roomNumber } }, select: { id: true } });
    if (existing) {
      room = await prisma.room.update({ where: { id: existing.id }, data: roomData });
      updated++;
    } else {
      room = await prisma.room.create({ data: (roomId ? { id: roomId, ...roomData } : roomData) as never });
      created++;
    }

    // 入居者（名前があり必須が揃えばupsert）
    const t = fromRow(row, TENANT_COLS);
    if (t.name && t.contractStart && t.contractEnd) {
      const tenantData = {
        ...t,
        phone: t.phone ?? "",
        guarantorCompany: t.guarantorCompany ?? "",
        guarantorContractNumber: t.guarantorContractNumber ?? "",
      };
      await prisma.tenant.upsert({
        where: { roomId: room.id },
        create: { roomId: room.id, ...tenantData } as never,
        update: tenantData as never,
      });
      tenants++;
    }
  }
  return { created, updated, skipped, tenants };
}

// ---- 全体復元（JSON） ----
async function restoreAll(json: {
  owners?: unknown[]; buildings?: unknown[]; rooms?: unknown[]; tenants?: unknown[];
  securityInfos?: unknown[]; repairHistories?: unknown[]; invoices?: unknown[];
}) {
  const ops = [
    // 削除（FK逆順）
    prisma.invoice.deleteMany(),
    prisma.repairHistory.deleteMany(),
    prisma.securityInfo.deleteMany(),
    prisma.tenant.deleteMany(),
    prisma.room.deleteMany(),
    prisma.building.deleteMany(),
    prisma.owner.deleteMany(),
    // 作成（FK順）
    prisma.owner.createMany({ data: (json.owners ?? []) as never }),
    prisma.building.createMany({ data: (json.buildings ?? []) as never }),
    prisma.room.createMany({ data: (json.rooms ?? []) as never }),
    prisma.tenant.createMany({ data: (json.tenants ?? []) as never }),
    prisma.securityInfo.createMany({ data: (json.securityInfos ?? []) as never }),
    prisma.repairHistory.createMany({ data: (json.repairHistories ?? []) as never }),
    prisma.invoice.createMany({ data: (json.invoices ?? []) as never }),
  ];
  await prisma.$transaction(ops);
  return {
    owners: json.owners?.length ?? 0,
    buildings: json.buildings?.length ?? 0,
    rooms: json.rooms?.length ?? 0,
    tenants: json.tenants?.length ?? 0,
  };
}

export async function POST(req: Request, props: { params: Promise<{ kind: string }> }) {
  const { kind } = await props.params;
  const form = await req.formData();
  const file = form.get("file") as File | null;
  if (!file) return NextResponse.json({ error: "ファイルが選択されていません" }, { status: 400 });

  try {
    const buf = Buffer.from(await file.arrayBuffer());

    let result: unknown;
    if (kind === "all") {
      const json = JSON.parse(buf.toString("utf-8"));
      if (!json || typeof json !== "object") throw new Error("バックアップJSONの形式が不正です");
      result = await restoreAll(json);
    } else {
      const rows = readSheet(buf);
      if (rows.length === 0) throw new Error("シートにデータ行がありません");
      if (kind === "buildings") result = await importBuildings(rows);
      else if (kind === "owners") result = await importOwners(rows);
      else if (kind === "rooms") result = await importRooms(rows);
      else return NextResponse.json({ error: "unknown import kind" }, { status: 400 });
    }

    revalidatePath("/");
    revalidatePath("/owners");
    return NextResponse.json({ success: true, result });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
