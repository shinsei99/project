/**
 * ヒーローの主役ビジュアル。Claude Code のセッションを模した画面。
 *
 * なぜ写真ではなくこれか:
 *   「ターミナルで動くエージェント」という立ち位置は、汎用のデスク写真では伝わらない。
 *   ここは説明ではなく**一目で分かる絵**が要るので、画面そのものを見せる。
 *   外部素材に依存しないぶん、崩れない・待たない・ライセンスの心配もない。
 *
 * 中身は実際の使い方に即した内容にしてある（作り話の出力を載せない）。
 */

const LINES: { kind: "prompt" | "user" | "tool" | "text" | "done"; text: string }[] = [
  { kind: "prompt", text: "~/projects/my-app" },
  { kind: "user", text: "決済後の画面が真っ白になる。原因を調べて直して" },
  { kind: "tool", text: "Grep  \"checkout\" src/" },
  { kind: "tool", text: "Read  src/app/checkout/complete.tsx" },
  { kind: "text", text: "決済APIの応答が null のとき、分岐せずに描画していました。" },
  { kind: "tool", text: "Edit  src/app/checkout/complete.tsx" },
  { kind: "tool", text: "Bash  npm test" },
  { kind: "done", text: "12 passed  —  修正して、テストも通っています" },
];

const STYLES = {
  prompt: "text-white/40",
  user: "text-white/95",
  tool: "text-sky-300/90",
  text: "text-white/70",
  done: "text-emerald-300",
} as const;

export function TerminalMock() {
  return (
    <div className="w-full overflow-hidden rounded-xl border border-white/10 bg-[#12151c] shadow-2xl shadow-black/25">
      {/* タイトルバー */}
      <div className="flex items-center gap-2 border-b border-white/10 bg-white/[0.04] px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-red-400/80" />
        <span className="size-2.5 rounded-full bg-yellow-400/80" />
        <span className="size-2.5 rounded-full bg-green-400/80" />
        <span className="ml-2 font-mono text-[11px] text-white/40">claude — my-app</span>
      </div>

      {/* 本文 */}
      <div className="space-y-1.5 p-4 font-mono text-[12px] leading-relaxed sm:text-[13px]">
        {LINES.map((l, i) => (
          <div key={i} className={`flex gap-2 ${STYLES[l.kind]}`}>
            <span aria-hidden className="shrink-0 select-none text-white/25">
              {l.kind === "user" ? ">" : l.kind === "tool" ? "⏺" : l.kind === "done" ? "✓" : "$"}
            </span>
            <span className="min-w-0 break-words">{l.text}</span>
          </div>
        ))}
        {/* カーソル */}
        <div className="flex gap-2 text-white/40">
          <span aria-hidden className="select-none text-white/25">&gt;</span>
          <span className="inline-block h-4 w-2 animate-pulse bg-white/50" />
        </div>
      </div>
    </div>
  );
}
