import { fieldsForType, formatBuildingValue, BuildingScope, BuildingFieldDef } from "@/lib/buildingFields";

const SCOPE_TITLE: Record<BuildingScope, string> = {
  common: "建物概要",
  マンション: "マンション情報",
  ビル: "ビル情報",
  駐車場: "駐車場情報",
  その他: "その他情報",
};

export function BuildingInfoPanel({
  buildingType,
  values,
}: {
  buildingType: string;
  values: Record<string, unknown>;
}) {
  const fields = fieldsForType(buildingType);
  const infoScopes: BuildingScope[] = ["common", buildingType as BuildingScope];
  const infoGroups = infoScopes
    .map((scope) => ({
      scope,
      defs: fields.filter((f) => f.scope === scope && formatBuildingValue(f, values[f.key]) !== null),
    }))
    .filter((g) => g.defs.length > 0);

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      <div className="px-6 py-4 border-b">
        <h2 className="font-semibold text-slate-700">🏢 建物情報</h2>
      </div>
      {infoGroups.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <p className="text-sm text-slate-400">
            建物情報が未登録です。「✨ 資料から建物情報をAI入力」でマイソクや謄本から自動入力できます。
          </p>
        </div>
      ) : (
        <div className="p-6 space-y-5">
          {infoGroups.map(({ scope, defs }) => (
            <section key={scope}>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">{SCOPE_TITLE[scope]}</h3>
              <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-2">
                {defs.map((f: BuildingFieldDef) => (
                  <div key={f.key} className="flex justify-between gap-4 border-b border-slate-50 py-1">
                    <dt className="text-sm text-slate-400 flex-shrink-0">{f.label}</dt>
                    <dd className="text-sm text-slate-700 font-medium text-right break-words">
                      {formatBuildingValue(f, values[f.key])}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
