import sharp from "sharp";
import { readFileSync } from "fs";

const svg = readFileSync("public/icon.svg");
// iOS のホーム画面用(180) と PWA マニフェスト用(192/512)
const sizes = [
  ["public/apple-touch-icon.png", 180],
  ["public/icon-192.png", 192],
  ["public/icon-512.png", 512],
];
for (const [path, size] of sizes) {
  await sharp(svg, { density: 400 }).resize(size, size).png().toFile(path);
  console.log(`${path} (${size}x${size})`);
}
