import { existsSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// claude CLI の実体パスを解決する。マシンによって設置先が違う
// （~/.local/bin か /opt/homebrew/bin）ため候補を順に探す。
// 環境変数 CLAUDE_BIN で明示指定も可能。
const CANDIDATES = [
  process.env.CLAUDE_BIN,
  join(homedir(), ".local/bin/claude"),
  "/opt/homebrew/bin/claude",
  "/usr/local/bin/claude",
].filter((p): p is string => !!p);

let cached: string | null = null;

export function resolveClaudeBin(): string {
  if (cached) return cached;
  for (const p of CANDIDATES) {
    if (existsSync(p)) {
      cached = p;
      return p;
    }
  }
  // 見つからなければ PATH 上の "claude" に賭ける（execFile が PATH を辿る）
  cached = "claude";
  return cached;
}
