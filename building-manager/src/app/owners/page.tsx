import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { OwnerRegisterButton } from "./OwnerRegisterButton";

export default async function OwnersPage() {
  const owners = await prisma.owner.findMany({
    include: { _count: { select: { buildings: true } } },
    orderBy: { createdAt: "asc" },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">👤 オーナー</h1>
          <p className="text-sm text-slate-400 mt-1">物件オーナーの一覧。1人で複数物件を所有できます。</p>
        </div>
        <OwnerRegisterButton />
      </div>

      {owners.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-12 text-center text-slate-400">
          <p className="text-lg">オーナーがまだ登録されていません</p>
          <p className="text-sm mt-2">「＋ オーナーを登録」から追加してください</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">法人名 / 名前</th>
                  <th className="px-4 py-3 text-left">電話</th>
                  <th className="px-4 py-3 text-left">FAX</th>
                  <th className="px-4 py-3 text-left">メール</th>
                  <th className="px-4 py-3 text-left">所有物件</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {owners.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link href={`/owners/${o.id}`} className="text-blue-600 hover:underline font-medium">
                        {o.company ? `${o.company}` : o.name}
                      </Link>
                      {o.company && <span className="text-slate-400 text-xs ml-2">{o.name}</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{o.phone ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-600">{o.fax ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-600">{o.email ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
                        {o._count.buildings}件
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
