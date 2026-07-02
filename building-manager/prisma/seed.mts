import { PrismaLibSql } from "@prisma/adapter-libsql";
import { PrismaClient } from "../src/generated/prisma/client";
import path from "path";

const dbPath = path.resolve(process.cwd(), "prisma/dev.db");
const adapter = new PrismaLibSql({ url: `file:${dbPath}` });
const prisma = new PrismaClient({ adapter });

async function main() {
  await prisma.invoice.deleteMany();
  await prisma.repairHistory.deleteMany();
  await prisma.securityInfo.deleteMany();
  await prisma.tenant.deleteMany();
  await prisma.room.deleteMany();
  await prisma.building.deleteMany();

  const mansion = await prisma.building.create({
    data: { name: "サンプルマンション", type: "マンション", address: "東京都渋谷区1-1-1" },
  });
  await prisma.room.create({
    data: { buildingId: mansion.id, roomNumber: "101", floor: 1, layout: "1K", status: "募集中", squareMeters: 25.5, rent: 65000 },
  });

  const building = await prisma.building.create({
    data: { name: "サンプルビル", type: "ビル", address: "東京都新宿区2-2-2" },
  });
  await prisma.room.create({
    data: { buildingId: building.id, roomNumber: "101", floor: 1, layout: "事務所", status: "募集中", squareMeters: 50.0, rent: 150000 },
  });

  console.log("Seed complete!");
}

main().finally(() => prisma.$disconnect());
