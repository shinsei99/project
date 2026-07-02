"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { createOwner, setBuildingOwner } from "@/app/actions";

export type OwnerLite = { id: string; company: string | null; name: string };
export type OwnerFull = OwnerLite & {
  address: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  note: string | null;
  buildingCount: number;
};

const OWNER_FIELDS: { key: keyof OwnerFull; label: string }[] = [
  { key: "company", label: "法人名" },
  { key: "name", label: "名前" },
  { key: "address", label: "住所" },
  { key: "phone", label: "電話番号" },
  { key: "fax", label: "FAX" },
  { key: "email", label: "メール" },
];

export function OwnerCard({
  buildingId,
  owner,
  allOwners,
}: {
  buildingId: string;
  owner: OwnerFull | null;
  allOwners: OwnerLite[];
}) {
  const [creating, setCreating] = useState(false);
  const [isPending, startTransition] = useTransition();

  function assign(ownerId: string) {
    startTransition(async () => {
      await setBuildingOwner(buildingId, ownerId);
    });
  }

  function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const name = (fd.get("name") as string)?.trim();
    if (!name) return;
    startTransition(async () => {
      await createOwner(
        {
          company: fd.get("company") as string,
          name,
          address: fd.get("address") as string,
          phone: fd.get("phone") as string,
          fax: fd.get("fax") as string,
          email: fd.get("email") as string,
        },
        buildingId,
      );
      setCreating(false);
    });
  }

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      <div className="px-6 py-4 border-b flex items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-700">👤 オーナー情報</h2>
        <div className="flex items-center gap-2">
          {/* 既存オーナーから選択 */}
          <select
            value={owner?.id ?? ""}
            onChange={(e) => assign(e.target.value)}
            disabled={isPending}
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 max-w-[200px]"
          >
            <option value="">未割当</option>
            {allOwners.map((o) => (
              <option key={o.id} value={o.id}>
                {o.company ? `${o.company}（${o.name}）` : o.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => setCreating((v) => !v)}
            className="text-sm border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors whitespace-nowrap"
          >
            ＋新規登録
          </button>
        </div>
      </div>

      <div className="p-6">
        {/* 新規オーナー登録フォーム */}
        {creating && (
          <form onSubmit={handleCreate} className="mb-6 border border-slate-200 rounded-xl p-4 bg-slate-50 space-y-3">
            <p className="text-sm font-semibold text-slate-700">新規オーナーを登録してこの物件に割当</p>
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div className="sm:col-span-2">
                <label className="block text-xs text-slate-500 mb-1">法人名</label>
                <input name="company" placeholder="〇〇不動産株式会社" className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">名前 *</label>
                <input name="name" required className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">電話番号</label>
                <input name="phone" className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs text-slate-500 mb-1">住所</label>
                <input name="address" className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">FAX</label>
                <input name="fax" className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">メール</label>
                <input name="email" className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={isPending} className="bg-blue-600 text-white text-sm rounded-lg px-4 py-2 hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {isPending ? "登録中..." : "登録して割当"}
              </button>
              <button type="button" onClick={() => setCreating(false)} className="border border-slate-200 text-sm rounded-lg px-4 py-2 hover:bg-white transition-colors">
                キャンセル
              </button>
            </div>
          </form>
        )}

        {/* 現在のオーナー表示 */}
        {owner ? (
          <div className="space-y-4">
            <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-2">
              {OWNER_FIELDS.map((f) => {
                const v = owner[f.key];
                if (!v) return null;
                return (
                  <div key={f.key} className="flex justify-between gap-4 border-b border-slate-50 py-1">
                    <dt className="text-sm text-slate-400 flex-shrink-0">{f.label}</dt>
                    <dd className="text-sm text-slate-700 font-medium text-right break-words">{String(v)}</dd>
                  </div>
                );
              })}
            </dl>
            <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
              <Link href={`/owners/${owner.id}`} className="text-sm text-blue-600 hover:underline">
                このオーナーの物件一覧
                {owner.buildingCount > 1 && (
                  <span className="ml-1 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">他{owner.buildingCount - 1}件所有</span>
                )}
                {" →"}
              </Link>
              <button onClick={() => assign("")} disabled={isPending} className="text-xs text-slate-400 hover:text-red-500 disabled:opacity-50">
                この物件からオーナーを解除
              </button>
            </div>
          </div>
        ) : (
          !creating && (
            <p className="text-sm text-slate-400">
              オーナー未割当です。上の選択で既存オーナーを割り当てるか「＋新規登録」で登録してください。謄本をAI入力した所有者名も、ここで登録できます。
            </p>
          )
        )}
      </div>
    </div>
  );
}
