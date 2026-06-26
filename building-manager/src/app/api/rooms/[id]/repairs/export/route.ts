import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(
  _request: Request,
  props: { params: Promise<{ id: string }> },
) {
  const { id } = await props.params;

  const room = await prisma.room.findUnique({
    where: { id },
    include: {
      building: true,
      repairs: {
        include: { invoice: true },
        orderBy: { date: "asc" },
      },
    },
  });

  if (!room) {
    return NextResponse.json({ error: "部屋が見つかりません" }, { status: 404 });
  }

  const rows = room.repairs.map((r, i) => ({
    "No.": i + 1,
    "対応日": new Date(r.date).toLocaleDateString("ja-JP"),
    "カテゴリ": r.category,
    "内容": r.description,
    "業者": r.contractor,
    "費用（税込）": r.costIncludingTax,
    "修繕詳細": r.invoice?.fileName ?? (r.invoice?.status === "保管済" ? "保管済" : "詳細なし"),
    "備考": r.notes ?? "",
  }));

  const XLSX = await import("xlsx");

  const ws = XLSX.utils.json_to_sheet(rows);
  ws["!cols"] = [
    { wch: 5 }, { wch: 13 }, { wch: 10 }, { wch: 40 },
    { wch: 20 }, { wch: 14 }, { wch: 10 }, { wch: 30 },
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "修繕履歴");

  const buf = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });

  const buildingName = room.building.name.replace(/[\\/:*?"<>|]/g, "_");
  const roomNum = room.roomNumber.replace(/[\\/:*?"<>|]/g, "_");
  const fileName = `修繕履歴_${buildingName}_${roomNum}号室.xlsx`;

  return new NextResponse(buf, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
    },
  });
}
