"use server";

import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { BUILDING_FIELD_MAP, coerceBuildingValue } from "@/lib/buildingFields";

export async function updateRoomStatus(roomId: string, status: string) {
  await prisma.room.update({ where: { id: roomId }, data: { status } });
  revalidatePath("/");
  revalidatePath(`/rooms/${roomId}`);
}

export async function upsertTenant(roomId: string, data: Record<string, string | boolean>) {
  const boolFields = ["support24", "earlyTermination"] as const;
  const intFields = ["condoFee", "waterFee", "supportFee", "depositAmount", "keyMoney", "renewalFee", "contractPeriodMonths"] as const;

  const payload: Record<string, unknown> = { ...data };
  for (const f of boolFields) payload[f] = data[f] === "true" || data[f] === true;
  for (const f of intFields) payload[f] = data[f] ? parseInt(data[f] as string, 10) : null;
  payload.contractStart = new Date(data.contractStart as string);
  payload.contractEnd = new Date(data.contractEnd as string);
  payload.moveInDate = data.moveInDate ? new Date(data.moveInDate as string) : null;
  delete payload.roomId;
  delete payload.rent_display;
  if (!payload.guarantorCompany) payload.guarantorCompany = "";
  if (!payload.guarantorContractNumber) payload.guarantorContractNumber = "";

  await prisma.tenant.upsert({
    where: { roomId },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    create: { roomId, ...(payload as any) },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    update: payload as any,
  });
  revalidatePath(`/rooms/${roomId}`);
}

export async function upsertSecurity(roomId: string, data: { keyOriginalNumber: string; electronicLockCode: string }) {
  await prisma.securityInfo.upsert({
    where: { roomId },
    create: { roomId, ...data },
    update: data,
  });
  revalidatePath(`/rooms/${roomId}`);
}

export async function addRepair(roomId: string, data: {
  date: string; category: string; description: string;
  contractor: string; costIncludingTax: string; notes: string;
}) {
  const repair = await prisma.repairHistory.create({
    data: {
      roomId,
      date: new Date(data.date),
      category: data.category,
      description: data.description,
      contractor: data.contractor,
      costIncludingTax: parseInt(data.costIncludingTax, 10),
      notes: data.notes || null,
    },
  });
  const invoice = await prisma.invoice.create({ data: { repairHistoryId: repair.id, status: "未保管" } });
  revalidatePath(`/rooms/${roomId}`);
  return { repairId: repair.id, invoiceId: invoice.id };
}

export async function saveRepairExcel(
  repairIds: string[],
  repairs: Array<{ date: string; category: string; description: string; contractor: string; costIncludingTax: number | string; notes?: string | null }>,
  roomId: string,
) {
  const XLSX = await import("xlsx");
  const { writeFileSync, mkdirSync } = await import("fs");
  const { join } = await import("path");

  const rows = repairs.map((r, i) => ({
    "No.": i + 1,
    "対応日": r.date,
    "カテゴリ": r.category,
    "内容": r.description,
    "業者": r.contractor,
    "費用（税込）": Number(r.costIncludingTax),
    "備考": r.notes ?? "",
  }));

  const ws = XLSX.utils.json_to_sheet(rows);
  ws["!cols"] = [{ wch: 5 }, { wch: 13 }, { wch: 10 }, { wch: 40 }, { wch: 20 }, { wch: 14 }, { wch: 30 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "修繕詳細");
  const buf: Buffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });

  const uploadDir = join(process.cwd(), "public", "uploads", "repairs");
  mkdirSync(uploadDir, { recursive: true });
  const fileName = `修繕詳細_${Date.now()}.xlsx`;
  writeFileSync(join(uploadDir, fileName), buf);
  const fileUrl = `/uploads/repairs/${fileName}`;

  for (const repairId of repairIds) {
    const inv = await prisma.invoice.findUnique({ where: { repairHistoryId: repairId } });
    if (inv) {
      await prisma.invoice.update({
        where: { id: inv.id },
        data: { fileUrl, fileName, status: "保管済", uploadedAt: new Date() },
      });
    }
  }
  revalidatePath(`/rooms/${roomId}`);
  return fileUrl;
}

export async function updateInvoiceStatus(
  invoiceId: string, roomId: string,
  status: string, fileUrl: string, fileName: string,
) {
  await prisma.invoice.update({
    where: { id: invoiceId },
    data: {
      status,
      fileUrl: fileUrl || null,
      fileName: fileName || null,
      uploadedAt: status === "保管済" ? new Date() : null,
    },
  });
  revalidatePath(`/rooms/${roomId}`);
}

export async function addRoom(buildingId: string, data: {
  roomNumber: string; floor: string; layout: string; status: string;
  squareMeters: string; rent: string;
}) {
  const room = await prisma.room.create({
    data: {
      buildingId,
      roomNumber: data.roomNumber,
      floor: parseInt(data.floor, 10) || 1,
      layout: data.layout || "—",
      status: data.status || "募集中",
      squareMeters: data.squareMeters ? parseFloat(data.squareMeters) : null,
      rent: data.rent ? parseInt(data.rent, 10) : null,
    },
  });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
  revalidatePath(`/buildings/${buildingId}/rooms`);
  return room.id;
}

export async function deleteRoom(roomId: string, buildingId: string) {
  await prisma.room.delete({ where: { id: roomId } });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
  revalidatePath(`/buildings/${buildingId}/rooms`);
  redirect(`/buildings/${buildingId}/rooms`);
}

export async function addBuilding(data: { name: string; type: string; address: string }) {
  const building = await prisma.building.create({ data });
  revalidatePath("/");
  return building.id;
}

export async function updateBuilding(buildingId: string, data: { name: string; type: string; address: string }) {
  await prisma.building.update({ where: { id: buildingId }, data });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
}

export async function deleteBuilding(buildingId: string) {
  await prisma.building.delete({ where: { id: buildingId } });
  revalidatePath("/");
  redirect("/");
}

// 自社の関与区分（管理 / 仲介）を保存。空文字なら未設定(null)。
export async function setBuildingHandling(buildingId: string, handling: string) {
  await prisma.building.update({
    where: { id: buildingId },
    data: { handling: handling || null },
  });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
}

// ===== オーナー（1人が複数物件を所有しうる独立エンティティ） =====

type OwnerInput = {
  company?: string;
  name: string;
  address?: string;
  phone?: string;
  fax?: string;
  email?: string;
  note?: string;
};

function normalizeOwner(data: OwnerInput) {
  return {
    company: data.company?.trim() || null,
    name: data.name.trim(),
    address: data.address?.trim() || null,
    phone: data.phone?.trim() || null,
    fax: data.fax?.trim() || null,
    email: data.email?.trim() || null,
    note: data.note?.trim() || null,
  };
}

export async function createOwner(data: OwnerInput, linkBuildingId?: string) {
  const owner = await prisma.owner.create({ data: normalizeOwner(data) });
  if (linkBuildingId) {
    await prisma.building.update({ where: { id: linkBuildingId }, data: { ownerId: owner.id } });
    revalidatePath(`/buildings/${linkBuildingId}`);
  }
  revalidatePath("/owners");
  revalidatePath("/");
  return owner.id;
}

export async function updateOwner(ownerId: string, data: OwnerInput) {
  await prisma.owner.update({ where: { id: ownerId }, data: normalizeOwner(data) });
  revalidatePath("/owners");
  revalidatePath(`/owners/${ownerId}`);
  revalidatePath("/");
}

export async function deleteOwner(ownerId: string) {
  // 紐づく物件は ownerId を外す（物件自体は残す）
  await prisma.building.updateMany({ where: { ownerId }, data: { ownerId: null } });
  await prisma.owner.delete({ where: { id: ownerId } });
  revalidatePath("/owners");
  revalidatePath("/");
}

// 物件にオーナーを割当（空文字で解除）
export async function setBuildingOwner(buildingId: string, ownerId: string) {
  await prisma.building.update({
    where: { id: buildingId },
    data: { ownerId: ownerId || null },
  });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
  revalidatePath("/owners");
}

// 建物レベルの詳細情報（構造・築年・戸数・オーナー等）を保存する。
// キーは BUILDING_FIELDS のものだけ受け付け、定義に沿って型変換する。
export async function updateBuildingInfo(buildingId: string, data: Record<string, unknown>) {
  const payload: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(data)) {
    if (key === "address") {
      // 住所は identity ではないので info 経由でも更新可
      payload.address = raw ? String(raw) : null;
      continue;
    }
    const def = BUILDING_FIELD_MAP[key];
    if (!def) continue; // 未知キー(name/type)は無視。identity変更は updateBuilding 側
    payload[key] = coerceBuildingValue(def, raw);
  }
  if (Object.keys(payload).length === 0) return;
  await prisma.building.update({ where: { id: buildingId }, data: payload });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
}
