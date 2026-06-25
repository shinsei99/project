import { openDB } from 'idb';
import type { User, SwimRecord, Goal } from './types';

const DB_NAME = 'swim-tracker';
const DB_VERSION = 1;

function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('users')) {
        db.createObjectStore('users', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('records')) {
        const rs = db.createObjectStore('records', { keyPath: 'id' });
        rs.createIndex('userId', 'userId');
      }
      if (!db.objectStoreNames.contains('goals')) {
        const gs = db.createObjectStore('goals', { keyPath: 'id' });
        gs.createIndex('userId', 'userId');
      }
      if (!db.objectStoreNames.contains('photos')) {
        db.createObjectStore('photos');
      }
      if (!db.objectStoreNames.contains('pools')) {
        db.createObjectStore('pools');
      }
    },
  });
}

export async function getUsers(): Promise<User[]> {
  const db = await getDB();
  return db.getAll('users');
}

export async function saveUser(user: User): Promise<void> {
  const db = await getDB();
  await db.put('users', user);
}

export async function deleteUser(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('users', id);
}

export async function getRecords(userId: string): Promise<SwimRecord[]> {
  const db = await getDB();
  return db.getAllFromIndex('records', 'userId', userId);
}

export async function saveRecord(record: SwimRecord): Promise<void> {
  const db = await getDB();
  await db.put('records', record);
}

export async function updateRecord(record: SwimRecord): Promise<void> {
  const db = await getDB();
  await db.put('records', record);
}

export async function deleteRecord(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('records', id);
}

export async function getGoals(userId: string): Promise<Goal[]> {
  const db = await getDB();
  return db.getAllFromIndex('goals', 'userId', userId);
}

export async function saveGoal(goal: Goal): Promise<void> {
  const db = await getDB();
  await db.put('goals', goal);
}

export async function deleteGoal(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('goals', id);
}

export async function getPhoto(userId: string): Promise<Blob | undefined> {
  const db = await getDB();
  return db.get('photos', userId);
}

export async function savePhoto(userId: string, blob: Blob): Promise<void> {
  const db = await getDB();
  await db.put('photos', blob, userId);
}

export async function deletePhoto(userId: string): Promise<void> {
  const db = await getDB();
  await db.delete('photos', userId);
}

export async function getPools(): Promise<string[]> {
  const db = await getDB();
  const val = await db.get('pools', 'list');
  return val ?? [];
}

export async function savePools(pools: string[]): Promise<void> {
  const db = await getDB();
  await db.put('pools', pools, 'list');
}
