"use client";

import { useState, useTransition } from "react";
import { updateInvoiceStatus } from "@/app/actions";

export function InvoiceForm({
  invoiceId, roomId, currentStatus, currentFileUrl, currentFileName,
}: {
  invoiceId: string; roomId: string;
  currentStatus: string; currentFileUrl: string; currentFileName: string;
}) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await updateInvoiceStatus(
        invoiceId, roomId,
        fd.get("status") as string,
        fd.get("fileUrl") as string,
        fd.get("fileName") as string,
      );
      setOpen(false);
    });
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-xs text-slate-500 hover:text-blue-600 hover:underline">
        修繕詳細を更新
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="font-semibold mb-4">修繕詳細・領収書情報</h3>
            <form onSubmit={handleSubmit} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs text-slate-500 mb-1">ステータス</label>
                <select name="status" defaultValue={currentStatus}
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="未保管">未保管</option>
                  <option value="保管済">保管済</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">ファイルURL / パス</label>
                <input name="fileUrl" defaultValue={currentFileUrl}
                  placeholder="https://... または /documents/..."
                  className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">ファイル名</label>
                <input name="fileName" defaultValue={currentFileName}
                  placeholder="invoice_101_2024.pdf"
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
