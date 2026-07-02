"use client";

import { useState, useTransition } from "react";
import { updateOwner } from "@/app/actions";

type OwnerValues = {
  company: string | null;
  name: string;
  address: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  note: string | null;
};

export function EditOwnerButton({ ownerId, values }: { ownerId: string; values: OwnerValues }) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const name = (fd.get("name") as string)?.trim();
    if (!name) return;
    startTransition(async () => {
      await updateOwner(ownerId, {
        company: fd.get("company") as string,
        name,
        address: fd.get("address") as string,
        phone: fd.get("phone") as string,
        fax: fd.get("fax") as string,
        email: fd.get("email") as string,
        note: fd.get("note") as string,
      });
      setOpen(false);
    });
  }

  const field = (name: keyof OwnerValues, label: string, required = false) => (
    <div>
      <label className="block text-xs text-slate-500 mb-1">{label}{required ? " *" : ""}</label>
      <input name={name} required={required} defaultValue={values[name] ?? ""}
        className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
    </div>
  );

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-sm border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">
        編集
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg my-6">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">オーナー情報を編集</h3>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-3 text-sm">
              {field("company", "法人名")}
              <div className="grid sm:grid-cols-2 gap-3">
                {field("name", "名前", true)}
                {field("phone", "電話番号")}
              </div>
              {field("address", "住所")}
              <div className="grid sm:grid-cols-2 gap-3">
                {field("fax", "FAX")}
                {field("email", "メール")}
              </div>
              {field("note", "備考")}
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={isPending} className="flex-1 bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {isPending ? "保存中..." : "保存"}
                </button>
                <button type="button" onClick={() => setOpen(false)} className="flex-1 border border-slate-200 rounded-lg py-2 hover:bg-slate-50 transition-colors">
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
