-- CreateTable
CREATE TABLE "Room" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "roomNumber" TEXT NOT NULL,
    "floor" INTEGER NOT NULL,
    "layout" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT '空室',
    "squareMeters" REAL,
    "rent" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Tenant" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "roomId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "email" TEXT,
    "guarantorCompany" TEXT NOT NULL,
    "guarantorContractNumber" TEXT NOT NULL,
    "contractStart" DATETIME NOT NULL,
    "contractEnd" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Tenant_roomId_fkey" FOREIGN KEY ("roomId") REFERENCES "Room" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "SecurityInfo" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "roomId" TEXT NOT NULL,
    "keyOriginalNumber" TEXT NOT NULL,
    "electronicLockCode" TEXT,
    CONSTRAINT "SecurityInfo_roomId_fkey" FOREIGN KEY ("roomId") REFERENCES "Room" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "RepairHistory" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "roomId" TEXT NOT NULL,
    "date" DATETIME NOT NULL,
    "category" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "contractor" TEXT NOT NULL,
    "costIncludingTax" INTEGER NOT NULL,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RepairHistory_roomId_fkey" FOREIGN KEY ("roomId") REFERENCES "Room" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Invoice" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "repairHistoryId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT '未保管',
    "fileUrl" TEXT,
    "fileName" TEXT,
    "uploadedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Invoice_repairHistoryId_fkey" FOREIGN KEY ("repairHistoryId") REFERENCES "RepairHistory" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Room_roomNumber_key" ON "Room"("roomNumber");

-- CreateIndex
CREATE UNIQUE INDEX "Tenant_roomId_key" ON "Tenant"("roomId");

-- CreateIndex
CREATE UNIQUE INDEX "SecurityInfo_roomId_key" ON "SecurityInfo"("roomId");

-- CreateIndex
CREATE UNIQUE INDEX "Invoice_repairHistoryId_key" ON "Invoice"("repairHistoryId");
