export type RoomType =
  | "living" | "dining" | "kitchen" | "bedroom" | "storage"
  | "bathroom" | "toilet" | "entrance" | "corridor" | "balcony" | "other";

export type EquipmentType =
  | "toilet" | "bath" | "sink" | "kitchen_sink" | "stove" | "washing_machine" | "other";

export interface Room {
  id: string;
  name: string;       // "LDK", "洋室6帖", etc.
  type: RoomType;
  size?: string;      // "16.5帖" etc.
  // normalized 0-100 grid coordinates (polygon vertices)
  polygon: [number, number][];
}

export interface Wall {
  from: [number, number];
  to: [number, number];
  type: "outer" | "inner" | "pillar";
}

export interface Pillar {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Equipment {
  type: EquipmentType;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number; // degrees
}

export interface Door {
  x: number;
  y: number;
  width: number;
  rotation: number; // degrees, 0=opens right
  swing: "left" | "right";
}

export interface Window {
  x: number;
  y: number;
  width: number;
  rotation: number;
}

export interface TextLabel {
  x: number;
  y: number;
  text: string;
  size: "small" | "medium" | "large";
}

export interface Compass {
  x: number;
  y: number;
  angle: number; // degrees offset from North (usually 0)
}

export interface FloorPlanJSON {
  canvas: { width: number; height: number };
  rooms: Room[];
  walls: Wall[];
  pillars: Pillar[];
  equipment: Equipment[];
  doors: Door[];
  windows: Window[];
  labels: TextLabel[];
  compass: Compass;
  scale?: string; // "1:100" etc.
}
