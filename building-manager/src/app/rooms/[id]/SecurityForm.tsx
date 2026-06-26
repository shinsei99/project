"use client";

import { useState, useTransition } from "react";
import { upsertSecurity } from "@/app/actions";

type SecurityData = { keyOriginalNumber: string; electronicLockCode: string | null } | null;

export function SecurityForm({ roomId, security }: { roomId: string; security: SecurityData }) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await upsertSecurity(roomId, {
        keyOriginalNumber: fd.get("keyOriginalNumber") as string,
        electronicLockCode: fd.get("electronicLockCode") as string,
      });
      setOpen(false);
    });
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-xs text-blue-600 hover:underline">
        {security ? "編集" : "+ セキュリティ情報を登録"}
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="font-semibold mb-4">セキュリティ情報</h3>
            <form onSubmit={handleSubmit} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs text-slate-500 mb-1">鍵原本番号 *</label>
                <input name="keyOriginalNumber" required defaultValue={security?.keyOriginalNumber}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">電子錠暗証番号</label>
                <input name="electronicLockCode" defaultValue={security?.electronicLockCode ?? ""}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
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
