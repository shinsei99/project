"use server";

import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

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
      status: data.status || "空室",
      squareMeters: data.squareMeters ? parseFloat(data.squareMeters) : null,
      rent: data.rent ? parseInt(data.rent, 10) : null,
    },
  });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
  return room.id;
}

export async function deleteRoom(roomId: string, buildingId: string) {
  await prisma.room.delete({ where: { id: roomId } });
  revalidatePath("/");
  revalidatePath(`/buildings/${buildingId}`);
  redirect(`/buildings/${buildingId}`);
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
