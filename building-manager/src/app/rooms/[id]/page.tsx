import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { StatusBadge } from "@/components/StatusBadge";
import { InvoiceBadge } from "@/components/InvoiceBadge";
import { StatusForm } from "./StatusForm";
import { TenantForm } from "./TenantForm";
import { SecurityForm } from "./SecurityForm";
import { RepairForm } from "./RepairForm";
import { InvoiceForm } from "./InvoiceForm";
import { AiExtractButton } from "./AiExtractButton";
import { AiRepairButton } from "./AiRepairButton";

export default async function RoomDetailPage(props: PageProps<"/rooms/[id]">) {
  const { id } = await props.params;

  const room = await prisma.room.findUnique({
    where: { id },
    include: {
      building: true,
      tenant: true,
      security: true,
      repairs: {
        include: { invoice: true },
        orderBy: { date: "desc" },
      },
    },
  });

  if (!room) notFound();

  const totalRepairCost = room.repairs.reduce((sum, r) => sum + r.costIncludingTax, 0);
  const t = room.tenant;
  const totalMonthly = t
    ? (room.rent ?? 0) + (t.condoFee ?? 0) + (t.waterFee ?? 0) + (t.supportFee ?? 0)
    : null;

  return (
    <div className="space-y-6">
      {/* パンくず + ヘッダー */}
      <div className="flex items-start justify-between">
        <div>
          <div className="mb-1">
            <Link href={`/buildings/${room.buildingId}`} className="text-sm text-blue-600 hover:underline">
              ← {room.building.name}
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-800">{room.roomNumber}号室</h1>
          <p className="text-sm text-slate-500 mt-1">
            {room.floor}F / {room.layout}
            {room.squareMeters ? ` / ${room.squareMeters}㎡` : ""}
            {room.rent ? ` / ¥${room.rent.toLocaleString()}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AiExtractButton roomId={room.id} />
          <StatusForm roomId={room.id} currentStatus={room.status} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 入居者・契約情報 */}
        <section className="bg-white rounded-xl shadow p-5 space-y-4">
          <h2 className="font-semibold text-slate-700 border-b pb-2">入居者・契約情報</h2>
          {t ? (
            <div className="space-y-4">
              {/* 基本 */}
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-slate-500">入居者名</dt>
                <dd className="font-medium">{t.name}</dd>
                <dt className="text-slate-500">連絡先</dt>
                <dd>{t.phone}</dd>
                {t.email && (
                  <>
                    <dt className="text-slate-500">メール</dt>
                    <dd>{t.email}</dd>
                  </>
                )}
                <dt className="text-slate-500">契約期間</dt>
                <dd>
                  {new Date(t.contractStart).toLocaleDateString("ja-JP")} 〜{" "}
                  {new Date(t.contractEnd).toLocaleDateString("ja-JP")}
                </dd>
              </dl>

              {/* 総月額 */}
              {totalMonthly !== null && (
                <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 flex items-center justify-between">
                  <div className="text-xs text-blue-700 space-y-0.5">
                    <p>賃料 ¥{(room.rent ?? 0).toLocaleString()}</p>
                    {t.condoFee ? <p>共益費 ¥{t.condoFee.toLocaleString()}</p> : null}
                    {t.waterFee ? <p>水道代 ¥{t.waterFee.toLocaleString()}</p> : null}
                    {t.supportFee ? <p>サポート24 ¥{t.supportFee.toLocaleString()}</p> : null}
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-blue-600">総月額</p>
                    <p className="text-xl font-bold text-blue-700">¥{totalMonthly.toLocaleString()}</p>
                  </div>
                </div>
              )}

              {/* 職業・実入居日 */}
              {(t.occupation || t.moveInDate) && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {t.occupation && (
                    <>
                      <dt className="text-slate-500">職業・勤務先</dt>
                      <dd>{t.occupation}</dd>
                    </>
                  )}
                  {t.moveInDate && (
                    <>
                      <dt className="text-slate-500">実入居日</dt>
                      <dd>{new Date(t.moveInDate).toLocaleDateString("ja-JP")}</dd>
                    </>
                  )}
                </dl>
              )}

              {/* 契約条件 */}
              {(t.depositAmount || t.keyMoney || t.renewalFee || t.contractPeriodMonths) && (
                <div className="border-t pt-3">
                  <p className="text-xs font-semibold text-slate-500 mb-2">契約条件</p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    {t.depositAmount != null && (
                      <><dt className="text-slate-500">敷金</dt><dd>¥{t.depositAmount.toLocaleString()}</dd></>
                    )}
                    {t.keyMoney != null && (
                      <><dt className="text-slate-500">礼金</dt><dd>¥{t.keyMoney.toLocaleString()}</dd></>
                    )}
                    {t.renewalFee != null && (
                      <><dt className="text-slate-500">更新料</dt><dd>¥{t.renewalFee.toLocaleString()}</dd></>
                    )}
                    {t.contractPeriodMonths != null && (
                      <><dt className="text-slate-500">契約期間</dt><dd>{t.contractPeriodMonths}ヶ月</dd></>
                    )}
                  </dl>
                </div>
              )}

              {/* 支払い */}
              {(t.paymentMethod || t.paymentAccountName) && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {t.paymentMethod && (
                    <>
                      <dt className="text-slate-500">支払い方法</dt>
                      <dd>{t.paymentMethod}</dd>
                    </>
                  )}
                  {t.paymentAccountName && (
                    <>
                      <dt className="text-slate-500">振込名義人</dt>
                      <dd className="font-mono">{t.paymentAccountName}</dd>
                    </>
                  )}
                </dl>
              )}

              {/* 緊急連絡先 */}
              {(t.emergencyContactName || t.emergencyContactPhone) && (
                <div className="border-t pt-3">
                  <p className="text-xs font-semibold text-slate-500 mb-2">緊急連絡先</p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    {t.emergencyContactName && (
                      <>
                        <dt className="text-slate-500">氏名</dt>
                        <dd>
                          {t.emergencyContactName}
                          {t.emergencyContactRelation && (
                            <span className="text-slate-400 ml-1">（{t.emergencyContactRelation}）</span>
                          )}
                        </dd>
                      </>
                    )}
                    {t.emergencyContactPhone && (
                      <>
                        <dt className="text-slate-500">電話</dt>
                        <dd>{t.emergencyContactPhone}</dd>
                      </>
                    )}
                  </dl>
                </div>
              )}

              {/* 保証会社 */}
              <div className="border-t pt-3">
                <p className="text-xs font-semibold text-slate-500 mb-2">保証会社</p>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <dt className="text-slate-500">保証会社</dt>
                  <dd>{t.guarantorCompany}</dd>
                  {t.guarantorPlan && (
                    <>
                      <dt className="text-slate-500">加入プラン</dt>
                      <dd>{t.guarantorPlan}</dd>
                    </>
                  )}
                  <dt className="text-slate-500">保証契約番号</dt>
                  <dd className="font-mono text-xs">{t.guarantorContractNumber}</dd>
                </dl>
              </div>

              {/* 特約・付帯設備 */}
              <div className="border-t pt-3 space-y-2">
                <p className="text-xs font-semibold text-slate-500">特約・付帯設備</p>
                <div className="flex gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-1 rounded-full border ${t.support24 ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                    {t.support24 ? "✓ サポート24加入" : "サポート24未加入"}
                  </span>
                  <span className={`text-xs px-2 py-1 rounded-full border ${t.earlyTermination ? "bg-orange-50 text-orange-700 border-orange-200" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
                    {t.earlyTermination ? "⚠ 短期解約違約金あり" : "短期解約違約金なし"}
                  </span>
                </div>
                {t.earlyTermination && t.earlyTerminationDetail && (
                  <p className="text-xs text-slate-500 bg-orange-50 rounded p-2">{t.earlyTerminationDetail}</p>
                )}
                {t.initialEquipment && (
                  <div>
                    <p className="text-xs text-slate-500 font-medium mb-1">初期付帯設備</p>
                    <p className="text-xs text-slate-600 bg-slate-50 rounded p-2">{t.initialEquipment}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">入居者情報なし</p>
          )}
          <TenantForm roomId={room.id} tenant={room.tenant} rent={room.rent} />
        </section>

        {/* セキュリティ情報 */}
        <section className="bg-white rounded-xl shadow p-5 space-y-4">
          <h2 className="font-semibold text-slate-700 border-b pb-2">セキュリティ情報</h2>
          {room.security ? (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-slate-500">鍵原本番号</dt>
              <dd className="font-mono font-medium">{room.security.keyOriginalNumber}</dd>
              <dt className="text-slate-500">電子錠暗証番号</dt>
              <dd className="font-mono">{room.security.electronicLockCode ?? "—"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-slate-400">セキュリティ情報なし</p>
          )}
          <SecurityForm roomId={room.id} security={room.security} />
        </section>
      </div>

      {/* 修繕履歴 */}
      <section className="bg-white rounded-xl shadow overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h2 className="font-semibold text-slate-700">修繕履歴</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {room.repairs.length}件 / 合計 ¥{totalRepairCost.toLocaleString()}（税込）
            </p>
          </div>
          <div className="flex items-center gap-2">
            <AiRepairButton roomId={room.id} />
            {room.repairs.length > 0 && (
              <a
                href={`/api/rooms/${room.id}/repairs/export`}
                download
                className="flex items-center gap-1.5 text-sm border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <span>📥</span> Excel出力
              </a>
            )}
            <RepairForm roomId={room.id} />
          </div>
        </div>

        {room.repairs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">対応日</th>
                  <th className="px-4 py-3 text-left">カテゴリ</th>
                  <th className="px-4 py-3 text-left">内容</th>
                  <th className="px-4 py-3 text-left">業者</th>
                  <th className="px-4 py-3 text-right">費用（税込）</th>
                  <th className="px-4 py-3 text-left">修繕詳細</th>
                  <th className="px-4 py-3 text-left">備考</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {room.repairs.map((repair) => (
                  <tr key={repair.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                      {new Date(repair.date).toLocaleDateString("ja-JP")}
                    </td>
                    <td className="px-4 py-3">
                      <span className="bg-slate-100 text-slate-700 text-xs px-2 py-0.5 rounded">
                        {repair.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-xs">{repair.description}</td>
                    <td className="px-4 py-3 text-slate-600">{repair.contractor}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      ¥{repair.costIncludingTax.toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        {repair.invoice && (
                          <>
                            <InvoiceBadge status={repair.invoice.status} />
                            {repair.invoice.fileUrl && (
                              <a
                                href={repair.invoice.fileUrl}
                                download
                                className="text-xs text-blue-600 hover:underline truncate max-w-[160px]"
                              >
                                📥 {repair.invoice.fileName ?? "修繕詳細.xlsx"}
                              </a>
                            )}
                            <InvoiceForm
                              invoiceId={repair.invoice.id}
                              roomId={room.id}
                              currentStatus={repair.invoice.status}
                              currentFileUrl={repair.invoice.fileUrl ?? ""}
                              currentFileName={repair.invoice.fileName ?? ""}
                            />
                          </>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs max-w-[120px]">
                      {repair.notes ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-center py-12 text-slate-400 text-sm">修繕履歴はありません</p>
        )}
      </section>
    </div>
  );
}
