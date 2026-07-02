"use client";

import { useRef, useState, useTransition } from "react";
import { updateBuildingInfo } from "@/app/actions";
import { fieldsForType, formatBuildingValue, BUILDING_FIELD_MAP } from "@/lib/buildingFields";

type ExtractedBuilding = Record<string, unknown> & {
  name?: string | null;
  type?: string | null;
  address?: string | null;
};

type ExtractResult = {
  building?: ExtractedBuilding | null;
  extractionNotes?: string | null;
};

// 抽出結果として画面に出す項目（住所＋種別に応じた建物項目）
function displayableKeys(building: ExtractedBuilding, type: string): string[] {
  const keys: string[] = [];
  if (building.address) keys.push("address");
  for (const f of fieldsForType(type)) {
    const v = building[f.key];
    if (v !== null && v !== undefined && v !== "") keys.push(f.key);
  }
  return keys;
}

function labelFor(key: string): string {
  if (key === "address") return "所在地";
  return BUILDING_FIELD_MAP[key]?.label ?? key;
}

function previewValue(key: string, val: unknown): string {
  if (key === "address") return String(val);
  const def = BUILDING_FIELD_MAP[key];
  return def ? (formatBuildingValue(def, val) ?? String(val)) : String(val);
}

export function AiBuildingExtractButton({ buildingId, buildingType }: { buildingId: string; buildingType: string }) {
  const [step, setStep] = useState<"idle" | "staged" | "uploading" | "preview" | "applying">("idle");
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ExtractResult | null>(null);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
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
    setFileNames(stagedFiles.map((f) => f.name));
    setStep("uploading");

    const fd = new FormData();
    stagedFiles.forEach((f) => fd.append("files", f));

    fetch(`/api/buildings/${buildingId}/ai-extract`, { method: "POST", body: fd })
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok || !json.success) throw new Error(json.error ?? "抽出に失敗しました");
        const result: ExtractResult = json.data;
        setData(result);
        const b = result.building ?? {};
        setSelected(new Set(displayableKeys(b, buildingType)));
        setStep("preview");
      })
      .catch((e) => {
        setError(e.message);
        setStep("staged");
      });
  }

  function toggle(key: string) {
    setSelected((prev) => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  }

  function handleApply() {
    const b = data?.building;
    if (!b) return;
    setStep("applying");
    startTransition(async () => {
      try {
        const payload: Record<string, unknown> = {};
        for (const key of selected) payload[key] = b[key];
        if (Object.keys(payload).length > 0) {
          await updateBuildingInfo(buildingId, payload);
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

  const building = data?.building ?? {};
  const keys = displayableKeys(building, buildingType);

  return (
    <>
      <button
        onClick={() => fileRef.current?.click()}
        className="flex items-center gap-2 bg-violet-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-violet-700 transition-colors shadow"
      >
        <span>✨</span> 資料から建物情報をAI入力
      </button>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.xls,.docx,.doc,.csv,.txt,.png,.jpg,.jpeg"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* ステージング */}
      {step === "staged" && (
        <div className="fixed inset-0 bg-black/50 flex items-end justify-center z-50 p-0 sm:items-center sm:p-4">
          <div className="bg-white rounded-t-2xl sm:rounded-xl shadow-xl w-full max-w-sm">
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">解析するファイル</h3>
              <button onClick={() => { setStep("idle"); setStagedFiles([]); }} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
            </div>
            <div className="px-4 pt-4 pb-2 space-y-2">
              <p className="text-xs text-slate-400 px-1">賃貸募集資料（マイソク）・登記簿謄本・重説などを追加</p>
              {stagedFiles.map((f) => (
                <div key={f.name} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm">
                  <span className="truncate text-slate-700 mr-2">{f.name}</span>
                  <button onClick={() => removeFile(f.name)} className="text-slate-400 hover:text-red-500 flex-shrink-0 text-lg leading-none">×</button>
                </div>
              ))}
              {stagedFiles.length < 5 && (
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full border-2 border-dashed border-slate-200 rounded-lg py-2 text-sm text-slate-400 hover:border-violet-400 hover:text-violet-600 transition-colors"
                >
                  + ファイルを追加（最大5件）
                </button>
              )}
              {error && <p className="text-xs text-red-600 pt-1">{error}</p>}
            </div>
            <div className="p-4 flex gap-2">
              <button onClick={startAnalysis} className="flex-1 bg-violet-600 text-white rounded-xl py-3 font-semibold hover:bg-violet-700 transition-colors text-sm">
                解析スタート（{stagedFiles.length}件）
              </button>
              <button onClick={() => { setStep("idle"); setStagedFiles([]); }} className="px-4 border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors text-sm text-slate-600">
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
            <div className="text-4xl mb-4 animate-pulse">✨</div>
            <p className="font-semibold text-slate-700 mb-2">AIが資料を解析中...</p>
            <p className="text-xs text-slate-400 mb-4">{fileNames.join("、")}</p>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full animate-pulse" style={{ width: "70%" }} />
            </div>
            <p className="text-xs text-slate-400 mt-3">通常30秒〜2分かかります</p>
          </div>
        </div>
      )}

      {/* エラー（トースト） */}
      {error && step !== "staged" && (
        <div className="fixed bottom-6 right-6 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl shadow-lg z-50 max-w-sm">
          <p className="font-medium mb-1">エラー</p>
          <p className="text-xs">{error}</p>
          <button onClick={() => setError(null)} className="absolute top-2 right-3 text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {/* プレビュー */}
      {step === "preview" && data && (
        <div className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl my-6">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">AI抽出結果 — 反映する項目を選択</h3>
                <p className="text-xs text-slate-400 mt-0.5">解析ファイル: {fileNames.join("、")}</p>
              </div>
              <button onClick={() => setStep("idle")} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
            </div>

            <div className="p-6 space-y-6">
              {building.name && (
                <p className="text-xs text-slate-400">
                  資料の名称: <span className="text-slate-600 font-medium">{String(building.name)}</span>
                  {building.type ? `（${String(building.type)}）` : ""}
                </p>
              )}

              {keys.length > 0 ? (
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-slate-700">建物情報（{keys.length}項目）</h4>
                    <div className="flex gap-3">
                      <button onClick={() => setSelected(new Set(keys))} className="text-xs text-blue-600 hover:underline">すべて選択</button>
                      <button onClick={() => setSelected(new Set())} className="text-xs text-slate-400 hover:underline">全解除</button>
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-1.5">
                    {keys.map((key) => (
                      <label key={key} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer border border-slate-100">
                        <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} className="mt-0.5 accent-violet-600" />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs text-slate-400">{labelFor(key)}</span>
                          <p className="text-sm text-slate-700 font-medium break-words">{previewValue(key, building[key])}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </section>
              ) : (
                <p className="text-center text-slate-400 py-8">資料から登録できる建物情報が見つかりませんでした。</p>
              )}

              {data.extractionNotes && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
                  <p className="font-medium mb-1">AIからの補足</p>
                  <p>{data.extractionNotes}</p>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t flex gap-3">
              <button
                onClick={handleApply}
                disabled={isPending || selected.size === 0}
                className="flex-1 bg-violet-600 text-white rounded-lg py-2.5 font-medium hover:bg-violet-700 disabled:opacity-40 transition-colors"
              >
                {isPending ? "保存中..." : `選択した${selected.size}項目を反映する`}
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
