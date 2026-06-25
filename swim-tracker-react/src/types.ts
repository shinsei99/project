export interface User {
  id: string;
  name: string;
  gender: '男子' | '女子';
  birthDate: string;
  createdAt: string;
}

export interface SwimRecord {
  id: string;
  userId: string;
  date: string;
  event: string;
  distance: number;
  course: string;
  timeSec: number;
  timeStr: string;
  reactionTime: number;
  qualifGrade: string;
  meetName: string;
  poolName: string;
  splitTimes: string;
  lapTimes: string;
  createdAt: string;
}

export interface Goal {
  id: string;
  userId: string;
  event: string;
  distance: number;
  course: string;
  targetSec: number;
  targetStr: string;
  deadline: string;
  memo: string;
  createdAt: string;
}
