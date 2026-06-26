"use client";
import { useTransition } from "react";
import { deleteRoom } from "@/app/actions";

export function DeleteRoomButton({
  roomId,
  buildingId,
  roomNumber,
}: {
  roomId: string;
  buildingId: string;
  roomNumber: string;
}) {
  const [isPending, startTransition] = useTransition();
  return (
    <button
      disabled={isPending}
      onClick={() => {
        if (!confirm(`${roomNumber}号室を削除しますか？この操作は元に戻せません。`)) return;
        startTransition(() => deleteRoom(roomId, buildingId));
      }}
      className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 hover:underline"
    >
      {isPending ? "削除中..." : "削除"}
    </button>
  );
}
