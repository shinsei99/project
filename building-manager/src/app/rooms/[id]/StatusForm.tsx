"use client";

import { useTransition } from "react";
import { updateRoomStatus } from "@/app/actions";
import { StatusBadge } from "@/components/StatusBadge";
import { ROOM_STATUSES } from "@/types";

export function StatusForm({ roomId, currentStatus }: { roomId: string; currentStatus: string }) {
  const [isPending, startTransition] = useTransition();

  return (
    <div className="flex items-center gap-2">
      <StatusBadge status={currentStatus} />
      <select
        disabled={isPending}
        value={currentStatus}
        onChange={(e) => startTransition(() => updateRoomStatus(roomId, e.target.value))}
        className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {ROOM_STATUSES.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
    </div>
  );
}
