"use client";

import { useState, useTransition } from "react";
import { addRepair } from "@/app/actions";
import { REPAIR_CATEGORIES } from "@/types";

export function RepairForm({ roomId }: { roomId: string }) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await addRepair(roomId, {
        date: fd.get("date") as string,
        category: fd.get("category") as string,
        description: fd.get("description") as string,
        contractor: fd.get("contractor") as string,
        costIncludingTax: fd.get("costIncludingTax") as string,
        notes: fd.get("notes") as string,
      });
      setOpen(false);
    });
  }

  return (
    <>
      <button onClick={() => setOpen(true)}
        className="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors">
        + 修繕を追加
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
            <h3 className="font-semibold mb-4">修繕履歴を追加</h3>
            <form onSubmit={handleSubmit} className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">対応日 *</label>
                  <input name="date" type="date" required defaultValue={new Date().toISOString().split("T")[0]}
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">カテゴリ *</label>
                  <select name="category" required
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {REPAIR_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">修繕内容 *</label>
                <textarea name="description" required rows={2}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">対応業者名 *</label>
                  <input name="contractor" required
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">費用（税込）*</label>
                  <input name="costIncludingTax" type="number" min="0" required
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">備考</label>
                <input name="notes"
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={isPending}
                  className="flex-1 bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {isPending ? "追加中..." : "追加"}
                </button>
                <button type="button" onClick={() => setOpen(false)}
                  className="flex-1 border border-slate-200 rounded-lg py-2 hover:bg-slate-50 transition-colors">
                  キャンセル
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
