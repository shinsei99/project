"use client";

import { useRef, useState, useTransition } from "react";
import { upsertTenant, upsertSecurity, addRepair } from "@/app/actions";

type ExtractedData = {
  tenant?: Record<string, unknown> | null;
  security?: { keyOriginalNumber?: string | null; electronicLockCode?: string | null } | null;
  repairs?: Array<{
    date?: string; category?: string; description?: string;
    contractor?: string; costIncludingTax?: number; notes?: string;
  }>;
  extractionNotes?: string | null;
};

const TENANT_LABELS: Record<string, string> = {
  name: "入居者名", phone: "電話番号", email: "メール",
  contractStart: "契約開始日", contractEnd: "契約終了日",
  moveInDate: "実入居日（鍵渡し日）", occupation: "職業・勤務先",
  condoFee: "共益費", waterFee: "水道代", supportFee: "サポート24費用",
  depositAmount: "敷金", keyMoney: "礼金", renewalFee: "更新料", contractPeriodMonths: "契約期間（月）",
  paymentMethod: "支払い方法", paymentAccountName: "振込名義人（カナ）",
  emergencyContactName: "緊急連絡先 氏名", emergencyContactRelation: "続柄", emergencyContactPhone: "緊急連絡先 電話",
  guarantorCompany: "保証会社", guarantorPlan: "加入プラン", guarantorContractNumber: "保証契約番号",
  support24: "24時間サポート", earlyTermination: "短期解約違約金", earlyTerminationDetail: "違約金詳細",
  initialEquipment: "初期付帯設備",
};

export function AiExtractButton({ roomId }: { roomId: string }) {
  const [step, setStep] = useState<"idle" | "staged" | "uploading" | "preview" | "applying">("idle");
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ExtractedData | null>(null);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<Set<string>>(new Set());
  const [applySecurity, setApplySecurity] = useState(false);
  const [selectedRepairs, setSelectedRepairs] = useState<Set<number>>(new Set());
  const [isPending, startTransition] = useTransition();
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    if (!picked.length) return;
    // 既存ファイルと合算して重複除去（名前ベース）
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

    fetch(`/api/rooms/${roomId}/ai-extract`, { method: "POST", body: fd })
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok || !json.success) throw new Error(json.error ?? "抽出に失敗しました");

        const extracted: ExtractedData = json.data;
        setData(extracted);

        const tenantKeys = new Set<string>();
        if (extracted.tenant) {
          for (const [k, v] of Object.entries(extracted.tenant)) {
            if (v !== null && v !== undefined && k in TENANT_LABELS) tenantKeys.add(k);
          }
        }
        setSelectedTenant(tenantKeys);
        setApplySecurity(!!(extracted.security?.keyOriginalNumber || extracted.security?.electronicLockCode));
        setSelectedRepairs(new Set((extracted.repairs ?? []).map((_, i) => i)));
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
        if (selectedTenant.size > 0 && data.tenant) {
          const payload: Record<string, string | boolean> = {};
          for (const key of selectedTenant) {
            const val = data.tenant[key];
            if (val !== null && val !== undefined) {
              payload[key] = String(val);
            }
          }
          const t = data.tenant as Record<string, unknown>;
          const requiredStr = ["name", "phone", "guarantorCompany", "guarantorContractNumber", "contractStart", "contractEnd"];
          for (const f of requiredStr) {
            if (!payload[f]) payload[f] = t[f] != null ? String(t[f]) : "";
          }
          if (payload.name && payload.contractStart && payload.contractEnd) {
            await upsertTenant(roomId, payload);
          }
        }

        if (applySecurity && data.security?.keyOriginalNumber) {
          await upsertSecurity(roomId, {
            keyOriginalNumber: data.security.keyOriginalNumber,
            electronicLockCode: data.security.electronicLockCode ?? "",
          });
        }

        for (const idx of selectedRepairs) {
          const rep = data.repairs?.[idx];
          if (rep?.date && rep?.description && rep?.contractor) {
            await addRepair(roomId, {
              date: rep.date,
              category: rep.category ?? "その他",
              description: rep.description,
              contractor: rep.contractor,
              costIncludingTax: String(rep.costIncludingTax ?? 0),
              notes: rep.notes ?? "",
            });
          }
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

  function toggleTenant(key: string) {
    setSelectedTenant((prev) => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  }
  function toggleRepair(idx: number) {
    setSelectedRepairs((prev) => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  }

  return (
    <>
      {/* トリガーボタン */}
      <button
        onClick={() => fileRef.current?.click()}
        className="flex items-center gap-2 bg-violet-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-violet-700 transition-colors shadow"
      >
        <span>✨</span> AIで自動入力
      </button>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.xls,.docx,.doc,.csv,.txt"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* ステージングモーダル（ファイル選択後・解析前） */}
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
                  className="w-full border-2 border-dashed border-slate-200 rounded-lg py-2 text-sm text-slate-400 hover:border-violet-400 hover:text-violet-600 transition-colors"
                >
                  + ファイルを追加（最大5件）
                </button>
              )}
              {error && <p className="text-xs text-red-600 pt-1">{error}</p>}
            </div>
            <div className="p-4 flex gap-2">
              <button
                onClick={startAnalysis}
                className="flex-1 bg-violet-600 text-white rounded-xl py-3 font-semibold hover:bg-violet-700 transition-colors text-sm"
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
            <div className="text-4xl mb-4 animate-pulse">✨</div>
            <p className="font-semibold text-slate-700 mb-2">AIが書類を解析中...</p>
            <p className="text-xs text-slate-400 mb-4">{fileNames.join("、")}</p>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full animate-pulse" style={{ width: "70%" }} />
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
                <h3 className="font-semibold text-slate-800">AI抽出結果 — 反映する項目を選択</h3>
                <p className="text-xs text-slate-400 mt-0.5">解析ファイル: {fileNames.join("、")}</p>
              </div>
              <button onClick={() => setStep("idle")} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
            </div>

            <div className="p-6 space-y-6">
              {data.tenant && Object.values(data.tenant).some((v) => v !== null) && (
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-slate-700">入居者・契約情報</h4>
                    <button
                      onClick={() => setSelectedTenant(new Set(Object.entries(data.tenant!).filter(([k, v]) => v !== null && k in TENANT_LABELS).map(([k]) => k)))}
                      className="text-xs text-blue-600 hover:underline"
                    >すべて選択</button>
                  </div>
                  <div className="space-y-1.5">
                    {Object.entries(data.tenant)
                      .filter(([k, v]) => v !== null && k in TENANT_LABELS)
                      .map(([key, val]) => (
                        <label key={key} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
                          <input type="checkbox" checked={selectedTenant.has(key)} onChange={() => toggleTenant(key)} className="mt-0.5 accent-violet-600" />
                          <div className="flex-1 min-w-0">
                            <span className="text-xs text-slate-400">{TENANT_LABELS[key]}</span>
                            <p className="text-sm text-slate-700 font-medium truncate">
                              {typeof val === "boolean" ? (val ? "はい" : "いいえ") : String(val)}
                            </p>
                          </div>
                        </label>
                      ))}
                  </div>
                </section>
              )}

              {data.security && (data.security.keyOriginalNumber || data.security.electronicLockCode) && (
                <section>
                  <h4 className="text-sm font-semibold text-slate-700 mb-3">セキュリティ情報</h4>
                  <label className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
                    <input type="checkbox" checked={applySecurity} onChange={(e) => setApplySecurity(e.target.checked)} className="mt-0.5 accent-violet-600" />
                    <div>
                      {data.security.keyOriginalNumber && <p className="text-sm text-slate-700"><span className="text-xs text-slate-400">鍵原本番号: </span>{data.security.keyOriginalNumber}</p>}
                      {data.security.electronicLockCode && <p className="text-sm text-slate-700"><span className="text-xs text-slate-400">電子錠: </span>{data.security.electronicLockCode}</p>}
                    </div>
                  </label>
                </section>
              )}

              {data.repairs && data.repairs.length > 0 && (
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-slate-700">修繕履歴（{data.repairs.length}件）</h4>
                    <button onClick={() => setSelectedRepairs(new Set(data.repairs!.map((_, i) => i)))} className="text-xs text-blue-600 hover:underline">すべて選択</button>
                  </div>
                  <div className="space-y-2">
                    {data.repairs.map((rep, i) => (
                      <label key={i} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer border border-slate-100">
                        <input type="checkbox" checked={selectedRepairs.has(i)} onChange={() => toggleRepair(i)} className="mt-0.5 accent-violet-600" />
                        <div className="flex-1 text-sm">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{rep.category}</span>
                            <span className="text-slate-400 text-xs">{rep.date}</span>
                            {rep.costIncludingTax ? <span className="text-xs font-medium text-slate-700">¥{Number(rep.costIncludingTax).toLocaleString()}</span> : null}
                          </div>
                          <p className="text-slate-700 mt-1">{rep.description}</p>
                          <p className="text-xs text-slate-400">{rep.contractor}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </section>
              )}

              {data.extractionNotes && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
                  <p className="font-medium mb-1">AIからの補足</p>
                  <p>{data.extractionNotes}</p>
                </div>
              )}

              {!data.tenant && !data.security && (!data.repairs || data.repairs.length === 0) && (
                <p className="text-center text-slate-400 py-8">書類から登録できる情報が見つかりませんでした。</p>
              )}
            </div>

            <div className="px-6 py-4 border-t flex gap-3">
              <button
                onClick={handleApply}
                disabled={isPending || (selectedTenant.size === 0 && !applySecurity && selectedRepairs.size === 0)}
                className="flex-1 bg-violet-600 text-white rounded-lg py-2.5 font-medium hover:bg-violet-700 disabled:opacity-40 transition-colors"
              >
                {step === "applying" ? "保存中..." : "選択した内容を反映する"}
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
