"use client";
import { useState, useTransition, useEffect } from "react";
import { upsertTenant } from "@/app/actions";
import { PAYMENT_METHODS } from "@/types";

type TenantData = {
  name: string;
  phone: string;
  email: string | null;
  occupation: string | null;
  moveInDate: Date | null;
  condoFee: number | null;
  waterFee: number | null;
  supportFee: number | null;
  depositAmount: number | null;
  keyMoney: number | null;
  renewalFee: number | null;
  contractPeriodMonths: number | null;
  paymentMethod: string | null;
  paymentAccountName: string | null;
  emergencyContactName: string | null;
  emergencyContactRelation: string | null;
  emergencyContactPhone: string | null;
  guarantorCompany: string;
  guarantorPlan: string | null;
  guarantorContractNumber: string;
  contractStart: Date;
  contractEnd: Date;
  support24: boolean;
  earlyTermination: boolean;
  earlyTerminationDetail: string | null;
  initialEquipment: string | null;
} | null;

function fmt(d: Date) {
  return new Date(d).toISOString().split("T")[0];
}

export function TenantForm({
  roomId,
  tenant,
  rent,
}: {
  roomId: string;
  tenant: TenantData;
  rent: number | null;
}) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [condoVal, setCondoVal] = useState(tenant?.condoFee ?? 0);
  const [waterVal, setWaterVal] = useState(tenant?.waterFee ?? 0);
  const [supportVal, setSupportVal] = useState(tenant?.supportFee ?? 0);
  const [earlyTerm, setEarlyTerm] = useState(tenant?.earlyTermination ?? false);

  const total = (rent ?? 0) + (condoVal || 0) + (waterVal || 0) + (supportVal || 0);

  useEffect(() => {
    if (open) {
      setCondoVal(tenant?.condoFee ?? 0);
      setWaterVal(tenant?.waterFee ?? 0);
      setSupportVal(tenant?.supportFee ?? 0);
      setEarlyTerm(tenant?.earlyTermination ?? false);
    }
  }, [open, tenant]);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const data: Record<string, string | boolean> = {};
    fd.forEach((v, k) => {
      data[k] = v as string;
    });
    data.support24 = (fd.get("support24") === "on").toString();
    data.earlyTermination = earlyTerm.toString();
    startTransition(async () => {
      await upsertTenant(roomId, data);
      setOpen(false);
    });
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-xs text-blue-600 hover:underline">
        {tenant ? "編集" : "+ 入居者情報を登録"}
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl my-4">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">入居者・契約情報</h3>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-6 text-sm">

              {/* 基本情報 */}
              <section>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  基本情報
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="入居者名 *" name="name" required defaultValue={tenant?.name} />
                  <Field label="電話番号 *" name="phone" required defaultValue={tenant?.phone} />
                  <Field
                    label="メールアドレス"
                    name="email"
                    type="email"
                    defaultValue={tenant?.email ?? ""}
                  />
                  <Field
                    label="職業・勤務先"
                    name="occupation"
                    defaultValue={tenant?.occupation ?? ""}
                    placeholder="会社員 / 株式会社〇〇"
                  />
                  <Field
                    label="実入居日（鍵渡し日）"
                    name="moveInDate"
                    type="date"
                    defaultValue={tenant?.moveInDate ? fmt(tenant.moveInDate) : ""}
                  />
                  <div className="col-span-2 grid grid-cols-2 gap-2">
                    <Field
                      label="契約開始日 *"
                      name="contractStart"
                      type="date"
                      required
                      defaultValue={tenant ? fmt(tenant.contractStart) : ""}
                    />
                    <Field
                      label="契約終了日 *"
                      name="contractEnd"
                      type="date"
                      required
                      defaultValue={tenant ? fmt(tenant.contractEnd) : ""}
                    />
                  </div>
                </div>
              </section>

              {/* 契約条件 */}
              <section>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  契約条件（敷金・礼金・更新）
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">敷金（円）</label>
                    <input name="depositAmount" type="number" min="0" defaultValue={tenant?.depositAmount ?? ""}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="0" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">礼金（円）</label>
                    <input name="keyMoney" type="number" min="0" defaultValue={tenant?.keyMoney ?? ""}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="0" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">更新料（円）</label>
                    <input name="renewalFee" type="number" min="0" defaultValue={tenant?.renewalFee ?? ""}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="0" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">契約期間（月）</label>
                    <input name="contractPeriodMonths" type="number" min="1" defaultValue={tenant?.contractPeriodMonths ?? ""}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="24" />
                  </div>
                </div>
              </section>

              {/* 請求・支払い情報 */}
              <section>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  請求・支払い情報
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">賃料（円）</label>
                    <input
                      type="text"
                      readOnly
                      value={rent ? `¥${rent.toLocaleString()}` : "—"}
                      className="w-full border border-slate-100 rounded-lg px-3 py-1.5 bg-slate-50 text-slate-400 text-sm cursor-not-allowed"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">共益費（円）</label>
                    <input
                      name="condoFee"
                      type="number"
                      min="0"
                      value={condoVal || ""}
                      onChange={(e) => setCondoVal(Number(e.target.value))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">水道代（円）</label>
                    <input
                      name="waterFee"
                      type="number"
                      min="0"
                      value={waterVal || ""}
                      onChange={(e) => setWaterVal(Number(e.target.value))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">緊急サポート24（円）</label>
                    <input
                      name="supportFee"
                      type="number"
                      min="0"
                      value={supportVal || ""}
                      onChange={(e) => setSupportVal(Number(e.target.value))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="0"
                    />
                  </div>
                </div>
                {/* 合計 */}
                <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex items-center justify-between">
                  <span className="text-sm font-semibold text-blue-800">総月額（請求合計）</span>
                  <span className="text-2xl font-bold text-blue-700">¥{total.toLocaleString()}</span>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">支払い方法</label>
                    <select
                      name="paymentMethod"
                      defaultValue={tenant?.paymentMethod ?? ""}
                      className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">選択してください</option>
                      {PAYMENT_METHODS.map((m) => (
                        <option key={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                  <Field
                    label="振込名義人（カナ）"
                    name="paymentAccountName"
                    defaultValue={tenant?.paymentAccountName ?? ""}
                    placeholder="ヤマダ タロウ"
                  />
                </div>
              </section>

              {/* 緊急連絡先・保証会社 */}
              <section>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  緊急連絡先・保証会社
                </h4>
                <div className="grid grid-cols-3 gap-3">
                  <Field
                    label="緊急連絡先 氏名"
                    name="emergencyContactName"
                    defaultValue={tenant?.emergencyContactName ?? ""}
                  />
                  <Field
                    label="続柄"
                    name="emergencyContactRelation"
                    defaultValue={tenant?.emergencyContactRelation ?? ""}
                    placeholder="父"
                  />
                  <Field
                    label="緊急連絡先 電話番号"
                    name="emergencyContactPhone"
                    defaultValue={tenant?.emergencyContactPhone ?? ""}
                  />
                  <Field
                    label="保証会社名 *"
                    name="guarantorCompany"
                    required
                    defaultValue={tenant?.guarantorCompany}
                  />
                  <Field
                    label="加入プラン"
                    name="guarantorPlan"
                    defaultValue={tenant?.guarantorPlan ?? ""}
                    placeholder="スタンダード"
                  />
                  <Field
                    label="保証契約番号 *"
                    name="guarantorContractNumber"
                    required
                    defaultValue={tenant?.guarantorContractNumber}
                  />
                </div>
              </section>

              {/* 特約・付帯設備 */}
              <section>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  特約・付帯設備
                </h4>
                <div className="space-y-3">
                  {/* 24時間安心サポート */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div>
                      <p className="font-medium text-slate-700">24時間安心サポート</p>
                      <p className="text-xs text-slate-400">緊急時の対応サービス加入状況</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        name="support24"
                        defaultChecked={tenant?.support24}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                  {/* 短期解約違約金 */}
                  <div className="bg-slate-50 rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between p-3">
                      <div>
                        <p className="font-medium text-slate-700">短期解約違約金</p>
                        <p className="text-xs text-slate-400">短期解約時のペナルティ設定</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={earlyTerm}
                          onChange={(e) => setEarlyTerm(e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
                      </label>
                    </div>
                    {earlyTerm && (
                      <div className="px-3 pb-3">
                        <textarea
                          name="earlyTerminationDetail"
                          rows={2}
                          defaultValue={tenant?.earlyTerminationDetail ?? ""}
                          placeholder="例：入居後1年未満の解約は賃料2ヶ月分を違約金として請求"
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none"
                        />
                      </div>
                    )}
                  </div>
                  {/* 初期付帯設備メモ */}
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      初期付帯設備メモ（退去時トラブル防止）
                    </label>
                    <textarea
                      name="initialEquipment"
                      rows={2}
                      defaultValue={tenant?.initialEquipment ?? ""}
                      placeholder="例：エアコン1台（1号機）、照明器具、下駄箱、浴室乾燥機"
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    />
                  </div>
                </div>
              </section>

              <div className="flex gap-2 pt-2 border-t">
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
                >
                  {isPending ? "保存中..." : "保存"}
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="flex-1 border border-slate-200 rounded-lg py-2.5 hover:bg-slate-50 transition-colors"
                >
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

function Field({
  label,
  name,
  type = "text",
  required,
  defaultValue,
  placeholder,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  defaultValue?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        required={required}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="w-full border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
      />
    </div>
  );
}
