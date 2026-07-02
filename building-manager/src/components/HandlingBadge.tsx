// 管理 / 仲介 区分の表示バッジ（サーバー・クライアント両用）
export function HandlingBadge({ handling }: { handling: string | null }) {
  const style =
    handling === "管理"
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : handling === "仲介"
        ? "bg-indigo-100 text-indigo-800 border-indigo-200"
        : "bg-slate-100 text-slate-400 border-slate-200";
  return (
    <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg text-xs font-bold border ${style}`}>
      {handling ?? "未設定"}
    </span>
  );
}
