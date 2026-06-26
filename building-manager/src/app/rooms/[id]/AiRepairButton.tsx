"use client";

import { useRef, useState, useTransition } from "react";
import { addRepair, saveRepairExcel } from "@/app/actions";

type RepairItem = {
  date?: string;
  category?: string;
  description?: string;
  contractor?: string;
  costIncludingTax?: number;
  notes?: string | null;
};

type ExtractedRepairs = {
  repairs: RepairItem[];
  extractionNotes?: string | null;
};

export function AiRepairButton({ roomId }: { roomId: string }) {
  const [step, setStep] = useState<"idle" | "staged" | "uploading" | "preview" | "applying">("idle");
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ExtractedRepairs | null>(null);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [isPending, startTransition] = useTransition();
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    if (!picked.length) return;
    setStagedFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      const merged = [...prev, ...picked.filter((f) => !existing.has(f.name))];
      if (merged.length > 5) {
        setError("最大5ファイルまでです。");
        return prev;
      }
      return merged;
    });
    setError(null);
    setStep("staged");
    if (fileRef.current) fileRef.current.value = "";
  }

  function removeFile(name: string) {
    setStagedFiles((prev) => {
      const next = prev.filter((f) => f.name !== name);
      if (next.length === 0) setStep("idle");
      return next;
    });
  }

  function startAnalysis() {
    if (!stagedFiles.length) return;
    const names = stagedFiles.map((f) => f.name);
    setFileNames(names);
    setStep("uploading");

    const fd = new FormData();
    stagedFiles.forEach((f) => fd.append("files", f));

    fetch(`/api/rooms/${roomId}/ai-repairs`, { method: "POST", body: fd })
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok || !json.success) throw new Error(json.error ?? "抽出に失敗しました");
        const extracted: ExtractedRepairs = json.data;
        setData(extracted);
        setSelected(new Set((extracted.repairs ?? []).map((_, i) => i)));
        setStep("preview");
      })
      .catch((e) => {
        setError(e.message);
        setStep("staged");
      });
  }

  function handleApply() {
    if (!data) return;
    setStep("applying");
    startTransition(async () => {
      try {
        const saved: { repairId: string; rep: NonNullable<typeof data.repairs>[number] }[] = [];
        for (const idx of selected) {
          const rep = data.repairs?.[idx];
          if (rep?.date && rep?.description && rep?.contractor) {
            const result = await addRepair(roomId, {
              date: rep.date,
              category: rep.category ?? "その他",
              description: rep.description,
              contractor: rep.contractor,
              costIncludingTax: String(rep.costIncludingTax ?? 0),
              notes: rep.notes ?? "",
            });
            saved.push({ repairId: result.repairId, rep });
          }
        }
        // 修繕詳細Excelを自動生成してアタッチ
        if (saved.length > 0) {
          await saveRepairExcel(
            saved.map((s) => s.repairId),
            saved.map((s) => ({
              date: s.rep.date ?? "",
              category: s.rep.category ?? "その他",
              description: s.rep.description ?? "",
              contractor: s.rep.contractor ?? "",
              costIncludingTax: s.rep.costIncludingTax ?? 0,
              notes: s.rep.notes ?? null,
            })),
            roomId,
          );
        }
        setStep("idle");
        setData(null);
        setStagedFiles([]);
        setFileNames([]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "保存に失敗しました");
        setStep("preview");
      }
    });
  }

  function toggle(idx: number) {
    setSelected((prev) => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  }

  return (
    <>
      <button
        onClick={() => fileRef.current?.click()}
        className="flex items-center gap-1.5 text-sm border border-emerald-300 text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg hover:bg-emerald-100 transition-colors"
      >
        <span>📄</span> AI修繕読込
      </button>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.xls,.docx,.doc,.csv,.txt"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* ステージングモーダル */}
      {step === "staged" && (
        <div className="fixed inset-0 bg-black/50 flex items-end justify-center z-50 p-0 sm:items-center sm:p-4">
          <div className="bg-white rounded-t-2xl sm:rounded-xl shadow-xl w-full max-w-sm">
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">解析するファイル</h3>
              <button onClick={() => { setStep("idle"); setStagedFiles([]); }} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
            </div>
            <div className="px-4 pt-4 pb-2 space-y-2">
              {stagedFiles.map((f) => (
                <div key={f.name} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm">
                  <span className="truncate text-slate-700 mr-2">{f.name}</span>
                  <button onClick={() => removeFile(f.name)} className="text-slate-400 hover:text-red-500 flex-shrink-0 text-lg leading-none">×</button>
                </div>
              ))}
              {stagedFiles.length < 5 && (
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full border-2 border-dashed border-slate-200 rounded-lg py-2 text-sm text-slate-400 hover:border-emerald-400 hover:text-emerald-600 transition-colors"
                >
                  + ファイルを追加（最大5件）
                </button>
              )}
              {error && <p className="text-xs text-red-600 pt-1">{error}</p>}
            </div>
            <div className="p-4 flex gap-2">
              <button
                onClick={startAnalysis}
                className="flex-1 bg-emerald-600 text-white rounded-xl py-3 font-semibold hover:bg-emerald-700 transition-colors text-sm"
              >
                解析スタート（{stagedFiles.length}件）
              </button>
              <button
                onClick={() => { setStep("idle"); setStagedFiles([]); }}
                className="px-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors text-sm text-slate-600"
              >
                キャンセル
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 解析中 */}
      {step === "uploading" && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-8 text-center max-w-sm w-full mx-4">
            <div className="text-4xl mb-4 animate-pulse">📄</div>
            <p className="font-semibold text-slate-700 mb-2">請求書を解析中...</p>
            <p className="text-xs text-slate-400 mb-4">{fileNames.join("、")}</p>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full animate-pulse" style={{ width: "70%" }} />
            </div>
            <p className="text-xs text-slate-400 mt-3">通常30秒〜2分かかります</p>
          </div>
        </div>
      )}

      {/* エラー */}
      {error && step !== "staged" && (
        <div className="fixed bottom-6 right-6 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl shadow-lg z-50 max-w-sm">
          <p className="font-medium mb-1">エラー</p>
          <p className="text-xs">{error}</p>
          <button onClick={() => setError(null)} className="absolute top-2 right-3 text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {/* プレビューモーダル */}
      {step === "preview" && data && (
        <div className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl my-6">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">AI修繕読込 — 登録する項目を選択</h3>
                <p className="text-xs text-slate-400 mt-0.5">解析ファイル: {fileNames.join("、")}</p>
              </div>
              <button onClick={() => setStep("idle")} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
            </div>

            <div className="p-6">
              {data.repairs && data.repairs.length > 0 ? (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-slate-700">修繕履歴（{data.repairs.length}件抽出）</h4>
                    <button onClick={() => setSelected(new Set(data.repairs.map((_, i) => i)))} className="text-xs text-blue-600 hover:underline">すべて選択</button>
                  </div>
                  <div className="space-y-2">
                    {data.repairs.map((rep, i) => (
                      <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 cursor-pointer border border-slate-100">
                        <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} className="mt-0.5 accent-emerald-600" />
                        <div className="flex-1 text-sm">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{rep.category ?? "その他"}</span>
                            <span className="text-slate-400 text-xs">{rep.date}</span>
                            {rep.costIncludingTax != null && <span className="text-xs font-medium text-slate-700">¥{Number(rep.costIncludingTax).toLocaleString()}（税込）</span>}
                          </div>
                          <p className="text-slate-700 font-medium">{rep.description}</p>
                          <p className="text-xs text-slate-400 mt-0.5">{rep.contractor}</p>
                          {rep.notes && <p className="text-xs text-slate-400 mt-0.5">備考: {rep.notes}</p>}
                        </div>
                      </label>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-center text-slate-400 py-8">書類から修繕履歴を抽出できませんでした。</p>
              )}
              {data.extractionNotes && (
                <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
                  <p className="font-medium mb-1">AIからの補足</p>
                  <p>{data.extractionNotes}</p>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t flex gap-3">
              <button
                onClick={handleApply}
                disabled={isPending || selected.size === 0}
                className="flex-1 bg-emerald-600 text-white rounded-lg py-2.5 font-medium hover:bg-emerald-700 disabled:opacity-40 transition-colors"
              >
                {step === "applying" ? "登録中..." : `選択した${selected.size}件を登録する`}
              </button>
              <button onClick={() => setStep("idle")} className="px-5 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors text-sm">
                キャンセル
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
