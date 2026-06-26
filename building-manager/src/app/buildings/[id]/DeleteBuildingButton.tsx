"use client";
import { useTransition } from "react";
import { deleteBuilding } from "@/app/actions";

export function DeleteBuildingButton({
  buildingId,
  buildingName,
}: {
  buildingId: string;
  buildingName: string;
}) {
  const [isPending, startTransition] = useTransition();
  return (
    <button
      disabled={isPending}
      onClick={() => {
        if (!confirm(`「${buildingName}」を削除しますか？この操作は元に戻せません。`)) return;
        startTransition(() => deleteBuilding(buildingId));
      }}
      className="text-xs text-red-500 hover:text-red-700 border border-red-200 px-3 py-1.5 rounded-lg disabled:opacity-50 hover:bg-red-50 transition-colors"
    >
      {isPending ? "削除中..." : "この物件を削除"}
    </button>
  );
}
