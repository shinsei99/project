"use client";

import { useState, useTransition } from "react";
import { updateBuilding } from "@/app/actions";
import { BUILDING_TYPES } from "@/types";

export function EditBuildingButton({
  buildingId,
  name,
  type,
  address,
}: {
  buildingId: string;
  name: string;
  type: string;
  address: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await updateBuilding(buildingId, {
        name: fd.get("name") as string,
        type: fd.get("type") as string,
        address: fd.get("address") as string,
      });
      setOpen(false);
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-sm border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
      >
        物件情報を編集
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">物件情報を編集</h3>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs text-slate-500 mb-1">種別</label>
                <select name="type" defaultValue={type}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {BUILDING_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">物件名 *</label>
                <input name="name" required defaultValue={name}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">住所</label>
                <input name="address" defaultValue={address ?? ""}
                  placeholder="東京都〇〇区..."
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={isPending}
                  className="flex-1 bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {isPending ? "保存中..." : "保存"}
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
