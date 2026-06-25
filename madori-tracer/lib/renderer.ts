import { FloorPlanJSON, Equipment, Door, Window } from "./types";

const SVG_SIZE = 800; // output SVG canvas size

function norm(v: number) {
  return (v / 100) * SVG_SIZE;
}

function pt([x, y]: [number, number]) {
  return `${norm(x)},${norm(y)}`;
}

// Equipment SVG icons (simplified line art)
function renderEquipment(eq: Equipment): string {
  const x = norm(eq.x);
  const y = norm(eq.y);
  const w = norm(eq.width);
  const h = norm(eq.height);
  const cx = x + w / 2;
  const cy = y + h / 2;
  const transform = eq.rotation ? ` transform="rotate(${eq.rotation},${cx},${cy})"` : "";

  switch (eq.type) {
    case "toilet":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>
        <ellipse cx="${cx}" cy="${y + h * 0.65}" rx="${w * 0.38}" ry="${h * 0.28}" fill="white" stroke="black" stroke-width="1.2"/>
        <rect x="${x + w * 0.1}" y="${y + h * 0.05}" width="${w * 0.8}" height="${h * 0.25}" rx="2" fill="white" stroke="black" stroke-width="1"/>
      </g>`;

    case "bath":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="white" stroke="black" stroke-width="1.5"/>
        <ellipse cx="${cx}" cy="${cy + h * 0.1}" rx="${w * 0.38}" ry="${h * 0.35}" fill="white" stroke="black" stroke-width="1.2"/>
        <rect x="${x + w * 0.1}" y="${y + h * 0.05}" width="${w * 0.8}" height="${h * 0.12}" rx="1" fill="#ddd" stroke="black" stroke-width="0.8"/>
      </g>`;

    case "sink":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>
        <ellipse cx="${cx}" cy="${cy}" rx="${w * 0.35}" ry="${h * 0.35}" fill="white" stroke="black" stroke-width="1.2"/>
        <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.06}" fill="black"/>
      </g>`;

    case "kitchen_sink":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="white" stroke="black" stroke-width="1.5"/>
        <rect x="${x + w * 0.05}" y="${y + h * 0.1}" width="${w * 0.42}" height="${h * 0.75}" rx="2" fill="white" stroke="black" stroke-width="1"/>
        <rect x="${x + w * 0.53}" y="${y + h * 0.1}" width="${w * 0.42}" height="${h * 0.75}" rx="2" fill="white" stroke="black" stroke-width="1"/>
      </g>`;

    case "stove":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="white" stroke="black" stroke-width="1.5"/>
        <circle cx="${x + w * 0.28}" cy="${cy}" r="${Math.min(w, h) * 0.18}" fill="white" stroke="black" stroke-width="1"/>
        <circle cx="${x + w * 0.72}" cy="${cy}" r="${Math.min(w, h) * 0.18}" fill="white" stroke="black" stroke-width="1"/>
        <circle cx="${cx}" cy="${y + h * 0.25}" r="${Math.min(w, h) * 0.12}" fill="white" stroke="black" stroke-width="1"/>
      </g>`;

    case "washing_machine":
      return `<g${transform}>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" fill="white" stroke="black" stroke-width="1.5"/>
        <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.35}" fill="white" stroke="black" stroke-width="1.2"/>
        <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.1}" fill="#ddd" stroke="black" stroke-width="0.8"/>
      </g>`;

    default:
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="white" stroke="black" stroke-width="1.2"${transform}/>`;
  }
}

// Door arc rendering
function renderDoor(door: Door): string {
  const x = norm(door.x);
  const y = norm(door.y);
  const w = norm(door.width);
  const cx = x;
  const cy = y;
  const transform = `rotate(${door.rotation},${x},${y})`;

  // Door leaf (line) + swing arc
  const arcX = door.swing === "right" ? x + w : x;
  const sweepFlag = door.swing === "right" ? 1 : 0;
  const endX = door.swing === "right" ? x + w : x - w;

  return `<g transform="${transform}">
    <line x1="${x}" y1="${y}" x2="${arcX}" y2="${y}" stroke="black" stroke-width="2"/>
    <path d="M ${arcX} ${cy} A ${w} ${w} 0 0 ${sweepFlag} ${endX} ${y + w}"
          fill="none" stroke="black" stroke-width="1" stroke-dasharray="4,2"/>
  </g>`;
}

// Window rendering (triple line style)
function renderWindow(win: Window): string {
  const x = norm(win.x);
  const y = norm(win.y);
  const w = norm(win.width);
  const transform = win.rotation ? ` transform="rotate(${win.rotation},${x},${y})"` : "";
  const gap = 2.5;

  return `<g${transform}>
    <line x1="${x}" y1="${y - gap}" x2="${x + w}" y2="${y - gap}" stroke="black" stroke-width="1"/>
    <line x1="${x}" y1="${y}" x2="${x + w}" y2="${y}" stroke="black" stroke-width="2.5"/>
    <line x1="${x}" y1="${y + gap}" x2="${x + w}" y2="${y + gap}" stroke="black" stroke-width="1"/>
  </g>`;
}

// Compass (N mark)
function renderCompass(x: number, y: number): string {
  const r = 18;
  return `<g>
    <circle cx="${x}" cy="${y}" r="${r}" fill="white" stroke="black" stroke-width="1.5"/>
    <polygon points="${x},${y - r + 4} ${x - 5},${y + 4} ${x + 5},${y + 4}" fill="black"/>
    <text x="${x}" y="${y + r - 4}" text-anchor="middle" font-family="'Noto Sans JP', sans-serif"
          font-size="10" font-weight="bold" fill="black">N</text>
  </g>`;
}

export function renderSVG(data: FloorPlanJSON): string {
  const parts: string[] = [];

  // Background
  parts.push(`<rect width="${SVG_SIZE}" height="${SVG_SIZE}" fill="white"/>`);

  // Room fills (white) + room name labels
  for (const room of data.rooms) {
    if (room.polygon.length < 3) continue;
    const points = room.polygon.map(pt).join(" ");
    parts.push(`<polygon points="${points}" fill="white" stroke="none"/>`);

    // Room label: center of bounding box
    const xs = room.polygon.map(([x]) => norm(x));
    const ys = room.polygon.map(([, y]) => norm(y));
    const lx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const ly = (Math.min(...ys) + Math.max(...ys)) / 2;
    const nameFontSize = room.name.length > 4 ? 11 : 13;

    parts.push(`<text x="${lx}" y="${ly - 6}" text-anchor="middle"
      font-family="'Noto Sans JP', sans-serif" font-size="${nameFontSize}" font-weight="bold" fill="black">${room.name}</text>`);
    if (room.size) {
      parts.push(`<text x="${lx}" y="${ly + 10}" text-anchor="middle"
        font-family="'Noto Sans JP', sans-serif" font-size="10" fill="#444">${room.size}</text>`);
    }
  }

  // Pillars (solid black)
  for (const p of data.pillars) {
    parts.push(`<rect x="${norm(p.x)}" y="${norm(p.y)}" width="${norm(p.width)}" height="${norm(p.height)}" fill="black"/>`);
  }

  // Windows
  for (const win of data.windows) {
    parts.push(renderWindow(win));
  }

  // Walls
  for (const wall of data.walls) {
    const strokeWidth = wall.type === "outer" ? 3.5 : 1.8;
    parts.push(`<line x1="${norm(wall.from[0])}" y1="${norm(wall.from[1])}"
      x2="${norm(wall.to[0])}" y2="${norm(wall.to[1])}"
      stroke="black" stroke-width="${strokeWidth}" stroke-linecap="square"/>`);
  }

  // Equipment
  for (const eq of data.equipment) {
    parts.push(renderEquipment(eq));
  }

  // Doors
  for (const door of data.doors) {
    parts.push(renderDoor(door));
  }

  // Compass
  const compassX = norm(data.compass.x);
  const compassY = norm(data.compass.y);
  parts.push(renderCompass(compassX, compassY));

  // Scale label
  if (data.scale) {
    parts.push(`<text x="10" y="${SVG_SIZE - 10}"
      font-family="'Noto Sans JP', sans-serif" font-size="10" fill="#666">縮尺 ${data.scale}</text>`);
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${SVG_SIZE}" height="${SVG_SIZE}" viewBox="0 0 ${SVG_SIZE} ${SVG_SIZE}">
  <defs>
    <style>
      text { font-family: 'Noto Sans JP', 'Yu Gothic', 'Hiragino Kaku Gothic ProN', sans-serif; }
    </style>
  </defs>
  ${parts.join("\n  ")}
</svg>`;
}
