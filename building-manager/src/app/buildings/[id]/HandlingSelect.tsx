"use client";

import { useState, useTransition } from "react";
import { setBuildingHandling } from "@/app/actions";
import { HANDLING_TYPES } from "@/types";

export function HandlingSelect({
  buildingId,
  value,
}: {
  buildingId: string;
  value: string | null;
}) {
  const [current, setCurrent] = useState(value ?? "");
  const [isPending, startTransition] = useTransition();

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    setCurrent(next);
    startTransition(async () => {
      await setBuildingHandling(buildingId, next);
    });
  }

  const accent =
    current === "管理"
      ? "border-emerald-300 text-emerald-800 bg-emerald-50"
      : current === "仲介"
        ? "border-indigo-300 text-indigo-800 bg-indigo-50"
        : "border-slate-200 text-slate-500 bg-white";

  return (
    <label className="inline-flex items-center gap-2 text-sm">
      <span className="text-xs text-slate-400">区分</span>
      <select
        value={current}
        onChange={handleChange}
        disabled={isPending}
        className={`border rounded-lg px-3 py-1.5 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${accent}`}
      >
        <option value="">未設定</option>
        {HANDLING_TYPES.map((h) => (
          <option key={h} value={h}>{h}</option>
        ))}
      </select>
    </label>
  );
}
