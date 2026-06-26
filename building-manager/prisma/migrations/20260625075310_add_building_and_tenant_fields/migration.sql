/*
  Warnings:

  - Added the required column `buildingId` to the `Room` table without a default value. This is not possible if the table is not empty.

*/
-- CreateTable
CREATE TABLE "Building" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "address" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Room" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "buildingId" TEXT NOT NULL,
    "roomNumber" TEXT NOT NULL,
    "floor" INTEGER NOT NULL,
    "layout" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT '空室',
    "squareMeters" REAL,
    "rent" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Room_buildingId_fkey" FOREIGN KEY ("buildingId") REFERENCES "Building" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_Room" ("createdAt", "floor", "id", "layout", "rent", "roomNumber", "squareMeters", "status", "updatedAt") SELECT "createdAt", "floor", "id", "layout", "rent", "roomNumber", "squareMeters", "status", "updatedAt" FROM "Room";
DROP TABLE "Room";
ALTER TABLE "new_Room" RENAME TO "Room";
CREATE UNIQUE INDEX "Room_buildingId_roomNumber_key" ON "Room"("buildingId", "roomNumber");
CREATE TABLE "new_Tenant" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "roomId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "email" TEXT,
    "condoFee" INTEGER,
    "waterFee" INTEGER,
    "supportFee" INTEGER,
    "paymentMethod" TEXT,
    "paymentAccountName" TEXT,
    "emergencyContactName" TEXT,
    "emergencyContactRelation" TEXT,
    "emergencyContactPhone" TEXT,
    "guarantorCompany" TEXT NOT NULL,
    "guarantorPlan" TEXT,
    "guarantorContractNumber" TEXT NOT NULL,
    "contractStart" DATETIME NOT NULL,
    "contractEnd" DATETIME NOT NULL,
    "support24" BOOLEAN NOT NULL DEFAULT false,
    "earlyTermination" BOOLEAN NOT NULL DEFAULT false,
    "earlyTerminationDetail" TEXT,
    "initialEquipment" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Tenant_roomId_fkey" FOREIGN KEY ("roomId") REFERENCES "Room" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_Tenant" ("contractEnd", "contractStart", "createdAt", "email", "guarantorCompany", "guarantorContractNumber", "id", "name", "phone", "roomId", "updatedAt") SELECT "contractEnd", "contractStart", "createdAt", "email", "guarantorCompany", "guarantorContractNumber", "id", "name", "phone", "roomId", "updatedAt" FROM "Tenant";
DROP TABLE "Tenant";
ALTER TABLE "new_Tenant" RENAME TO "Tenant";
CREATE UNIQUE INDEX "Tenant_roomId_key" ON "Tenant"("roomId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
