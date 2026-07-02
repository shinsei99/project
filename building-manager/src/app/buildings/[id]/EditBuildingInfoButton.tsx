"use client";

import { useState, useTransition } from "react";
import { updateBuildingInfo } from "@/app/actions";
import { fieldsForType, BuildingScope, BuildingFieldDef } from "@/lib/buildingFields";

const SCOPE_TITLE: Record<BuildingScope, string> = {
  common: "共通",
  マンション: "マンション情報",
  ビル: "ビル情報",
  駐車場: "駐車場情報",
  その他: "その他情報",
};

export function EditBuildingInfoButton({
  buildingId,
  buildingType,
  values,
}: {
  buildingId: string;
  buildingType: string;
  values: Record<string, unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const fields = fieldsForType(buildingType);
  const grouped: [BuildingScope, BuildingFieldDef[]][] = (
    ["common", buildingType as BuildingScope] as BuildingScope[]
  ).map((scope) => [scope, fields.filter((f) => f.scope === scope)]);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.type === "bool") {
        payload[f.key] = fd.get(f.key) === "on";
      } else {
        payload[f.key] = fd.get(f.key) ?? "";
      }
    }
    startTransition(async () => {
      await updateBuildingInfo(buildingId, payload);
      setOpen(false);
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-sm border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
      >
        建物情報を編集
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl my-6">
            <div className="px-6 py-4 border-b flex items-center justify-between sticky top-0 bg-white rounded-t-xl">
              <h3 className="font-semibold">建物情報を編集</h3>
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="p-6 space-y-6">
                {grouped.map(([scope, defs]) =>
                  defs.length === 0 ? null : (
                    <section key={scope}>
                      <h4 className="text-sm font-semibold text-slate-700 mb-3">{SCOPE_TITLE[scope]}</h4>
                      <div className="grid sm:grid-cols-2 gap-3">
                        {defs.map((f) => (
                          <div key={f.key} className={["note", "facilities"].includes(f.key) ? "sm:col-span-2" : ""}>
                            <label className="block text-xs text-slate-500 mb-1">
                              {f.label}{f.unit ? `（${f.unit}）` : ""}
                            </label>
                            {f.type === "bool" ? (
                              <label className="flex items-center gap-2 text-sm text-slate-700 py-1.5">
                                <input type="checkbox" name={f.key} defaultChecked={values[f.key] === true} className="accent-violet-600" />
                                あり
                              </label>
                            ) : (
                              <input
                                name={f.key}
                                defaultValue={values[f.key] != null ? String(values[f.key]) : ""}
                                placeholder={f.placeholder ?? ""}
                                inputMode={f.type === "int" || f.type === "float" ? "decimal" : undefined}
                                className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    </section>
                  ),
                )}
              </div>
              <div className="px-6 py-4 border-t flex gap-3 sticky bottom-0 bg-white rounded-b-xl">
                <button type="submit" disabled={isPending}
                  className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {isPending ? "保存中..." : "保存"}
                </button>
                <button type="button" onClick={() => setOpen(false)}
                  className="px-5 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors text-sm">
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
