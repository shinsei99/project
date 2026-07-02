"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

type ImportKind = "all" | "buildings" | "rooms" | "owners";

const EXCEL_DBS: { kind: ImportKind; title: string; desc: string }[] = [
  { kind: "buildings", title: "建物データベース", desc: "建物の基本情報・建物詳細・管理/仲介区分・オーナーID" },
  { kind: "rooms", title: "部屋＋入居者データベース", desc: "1部屋1行。部屋情報と入居者情報を同じ行にまとめて出力" },
  { kind: "owners", title: "オーナーデータベース", desc: "オーナーの法人名・名前・住所・電話・FAX・メール" },
];

function ImportButton({
  kind,
  accept,
  label,
  destructive,
  onDone,
}: {
  kind: ImportKind;
  accept: string;
  label: string;
  destructive?: boolean;
  onDone: (msg: string, ok: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function handle(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (ref.current) ref.current.value = "";
    if (!file) return;
    if (destructive && !confirm("全データを上書き復元します。現在のデータは失われます。よろしいですか？")) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/import/${kind}`, { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok || !json.success) throw new Error(json.error ?? "インポートに失敗しました");
      onDone(`インポート完了: ${JSON.stringify(json.result)}`, true);
    } catch (err) {
      onDone(err instanceof Error ? err.message : "インポートに失敗しました", false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => ref.current?.click()}
        disabled={busy}
        className={`text-sm px-4 py-2 rounded-lg border transition-colors disabled:opacity-50 ${
          destructive
            ? "border-red-200 text-red-600 hover:bg-red-50"
            : "border-slate-200 text-slate-700 hover:bg-slate-50"
        }`}
      >
        {busy ? "処理中..." : label}
      </button>
      <input ref={ref} type="file" accept={accept} className="hidden" onChange={handle} />
    </>
  );
}

const EXPORT_PIN = "4242";

export function SettingsClient() {
  const router = useRouter();
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [pinInput, setPinInput] = useState("");
  const [unlocked, setUnlocked] = useState(false);

  function onDone(msg: string, ok: boolean) {
    setToast({ msg, ok });
    if (ok) router.refresh();
    setTimeout(() => setToast(null), 6000);
  }

  // エクスポートは暗証番号4242でロック解除。解除後はURLにpinを付与してダウンロード。
  const exportHref = (kind: string) => (unlocked ? `/api/export/${kind}?pin=${EXPORT_PIN}` : undefined);

  function tryUnlock() {
    if (pinInput === EXPORT_PIN) {
      setUnlocked(true);
      onDone("エクスポートのロックを解除しました", true);
    } else {
      onDone("暗証番号が違います", false);
    }
  }

  function ExportLink({ kind, className, children }: { kind: string; className: string; children: React.ReactNode }) {
    if (!unlocked) {
      return (
        <button
          onClick={() => onDone("先に暗証番号（4242）でロックを解除してください", false)}
          className={`${className} opacity-50 cursor-not-allowed`}
        >
          🔒 {children}
        </button>
      );
    }
    return (
      <a href={exportHref(kind)} className={className}>
        {children}
      </a>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">⚙️ 設定</h1>
        <p className="text-sm text-slate-400 mt-1">データのエクスポート／インポート（バックアップ・移行用）</p>
      </div>

      {/* エクスポート ロック（暗証番号 4242） */}
      <div className={`rounded-xl border px-6 py-4 ${unlocked ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`}>
        {unlocked ? (
          <p className="text-sm text-emerald-800 font-medium">🔓 エクスポートのロックを解除中です。</p>
        ) : (
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <p className="text-sm font-medium text-amber-800">🔒 エクスポートには暗証番号が必要です</p>
              <p className="text-xs text-amber-700 mt-0.5">全データ・オーナー個人情報を含むため保護しています。</p>
            </div>
            <input
              type="password"
              inputMode="numeric"
              value={pinInput}
              onChange={(e) => setPinInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && tryUnlock()}
              placeholder="暗証番号"
              className="border border-amber-300 rounded-lg px-3 py-1.5 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <button onClick={tryUnlock} className="text-sm px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-colors">
              解除
            </button>
          </div>
        )}
      </div>

      {/* 全体バックアップ */}
      <section className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-slate-700">全データ バックアップ（JSON）</h2>
          <p className="text-xs text-slate-400 mt-0.5">建物・部屋・入居者・鍵・修繕・請求書・オーナーの全テーブルを完全保存／復元。別PCへの移行に。</p>
        </div>
        <div className="p-6 flex flex-wrap gap-3">
          <ExportLink kind="all" className="text-sm px-4 py-2 rounded-lg bg-slate-800 text-white hover:bg-slate-700 transition-colors">
            ⬇ 全データをエクスポート（JSON）
          </ExportLink>
          <ImportButton kind="all" accept=".json" label="⬆ 全データをインポート（復元・上書き）" destructive onDone={onDone} />
        </div>
      </section>

      {/* DB別 Excel */}
      <section className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-slate-700">データベース別 Excel</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            各DBをExcelで出力・取込。取込はID一致で更新、IDが空なら新規追加（部分更新・追記が可能）。
          </p>
        </div>
        <div className="divide-y divide-slate-100">
          {EXCEL_DBS.map((db) => (
            <div key={db.kind} className="px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
              <div>
                <p className="font-medium text-slate-800 text-sm">{db.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">{db.desc}</p>
              </div>
              <div className="flex items-center gap-2">
                <ExportLink kind={db.kind} className="text-sm px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
                  ⬇ エクスポート
                </ExportLink>
                <ImportButton kind={db.kind} accept=".xlsx,.xls" label="⬆ インポート" onDone={onDone} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <p className="text-xs text-slate-400">
        ※ Excelインポートで安全に往復させるには、まず「エクスポート」で出力したファイルを編集して取り込むのが確実です（ID列で照合します）。
      </p>

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 max-w-md px-4 py-3 rounded-xl shadow-lg text-sm border ${
            toast.ok ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-red-50 border-red-200 text-red-700"
          }`}
        >
          <p className="break-words">{toast.msg}</p>
        </div>
      )}
    </div>
  );
}
