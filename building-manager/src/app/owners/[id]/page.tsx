import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { EditOwnerButton } from "./EditOwnerButton";
import { DeleteOwnerButton } from "./DeleteOwnerButton";

const OWNER_FIELDS: { key: "company" | "name" | "address" | "phone" | "fax" | "email" | "note"; label: string }[] = [
  { key: "company", label: "法人名" },
  { key: "name", label: "名前" },
  { key: "address", label: "住所" },
  { key: "phone", label: "電話番号" },
  { key: "fax", label: "FAX" },
  { key: "email", label: "メール" },
  { key: "note", label: "備考" },
];

export default async function OwnerDetailPage(props: PageProps<"/owners/[id]">) {
  const { id } = await props.params;
  const owner = await prisma.owner.findUnique({
    where: { id },
    include: { buildings: { include: { rooms: true }, orderBy: { createdAt: "asc" } } },
  });
  if (!owner) notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="mb-1">
            <Link href="/owners" className="text-sm text-blue-600 hover:underline">← オーナー一覧</Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">{owner.company || owner.name}</h1>
          {owner.company && <p className="text-sm text-slate-400 mt-1">{owner.name}</p>}
        </div>
        <div className="flex items-center gap-2">
          <EditOwnerButton
            ownerId={owner.id}
            values={{
              company: owner.company, name: owner.name, address: owner.address,
              phone: owner.phone, fax: owner.fax, email: owner.email, note: owner.note,
            }}
          />
          <DeleteOwnerButton ownerId={owner.id} ownerName={owner.company || owner.name} />
        </div>
      </div>

      {/* 連絡先 */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b"><h2 className="font-semibold text-slate-700">連絡先</h2></div>
        <div className="p-6">
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
        </div>
      </div>

      {/* 所有物件 */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-slate-700">所有物件（{owner.buildings.length}件）</h2>
        </div>
        {owner.buildings.length === 0 ? (
          <p className="px-6 py-8 text-center text-sm text-slate-400">紐づく物件はありません。</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {owner.buildings.map((b) => (
              <Link key={b.id} href={`/buildings/${b.id}`} className="flex items-center justify-between px-6 py-3 hover:bg-slate-50">
                <div>
                  <span className="font-medium text-slate-800">{b.name}</span>
                  <span className="text-xs text-slate-400 ml-2">{b.type}</span>
                </div>
                <span className="text-sm text-slate-500">{b.rooms.length}室 →</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
