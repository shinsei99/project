"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

type Counter = { created: number; updated: number };
type SyncReport = {
  ok: boolean;
  buildings: Counter;
  rooms: Counter;
  tenants: Counter;
  owners: Counter;
  warnings: string[];
  errors: string[];
};

export function SyncButton() {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<SyncReport | null>(null);
  const router = useRouter();

  async function handleSync() {
    setLoading(true);
    setReport(null);
    try {
      const res = await fetch("/api/sync/rentroll", { method: "POST" });
      const data = (await res.json()) as SyncReport;
      setReport(data);
      router.refresh();
    } catch (e) {
      setReport({
        ok: false,
        buildings: { created: 0, updated: 0 },
        rooms: { created: 0, updated: 0 },
        tenants: { created: 0, updated: 0 },
        owners: { created: 0, updated: 0 },
        warnings: [],
        errors: [(e as Error).message],
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={handleSync}
        disabled={loading}
        title="Dropboxのレントロール（ビル/マンション/駐車場）と管理物件台帳を読み込んで最新化します"
        className="bg-emerald-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
      >
        {loading ? (
          <>
            <span className="inline-block h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            同期中...
          </>
        ) : (
          <>🔄 今すぐ同期</>
        )}
      </button>

      {report && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setReport(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              {report.ok ? "✅ 同期が完了しました" : "⚠️ 同期は完了しましたが一部エラーがあります"}
            </h3>
            <div className="text-sm space-y-1 text-slate-700">
              <p>物件: 新規 {report.buildings.created} / 更新 {report.buildings.updated}</p>
              <p>部屋・区画: 反映 {report.rooms.created} 件</p>
              <p>入居者: 反映 {report.tenants.created} 件</p>
              <p>オーナー: 新規 {report.owners.created}</p>
            </div>
            {report.warnings.length > 0 && (
              <div className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg p-2 space-y-1">
                {report.warnings.map((w, i) => (
                  <p key={i}>⚠ {w}</p>
                ))}
              </div>
            )}
            {report.errors.length > 0 && (
              <div className="mt-3 text-xs text-red-700 bg-red-50 rounded-lg p-2 space-y-1">
                {report.errors.map((e, i) => (
                  <p key={i}>✕ {e}</p>
                ))}
              </div>
            )}
            <button
              onClick={() => setReport(null)}
              className="mt-4 w-full border border-slate-200 rounded-lg py-2 text-sm hover:bg-slate-50 transition-colors"
            >
              閉じる
            </button>
          </div>
        </div>
      )}
    </>
  );
}
