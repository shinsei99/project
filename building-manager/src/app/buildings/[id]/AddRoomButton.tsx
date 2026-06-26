"use client";
import { useState, useTransition } from "react";
import { addRoom } from "@/app/actions";
import { useRouter } from "next/navigation";

export function AddRoomButton({ buildingId }: { buildingId: string }) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await addRoom(buildingId, {
        roomNumber: fd.get("roomNumber") as string,
        floor: "",
        layout: "",
        status: "空室",
        squareMeters: "",
        rent: "",
      });
      setOpen(false);
      router.refresh();
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="bg-blue-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
      >
        + 部屋を追加
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-xs p-6">
            <h3 className="font-semibold mb-1">部屋を追加</h3>
            <p className="text-xs text-slate-400 mb-4">間取り・賃料などはAI入力で後から登録できます</p>
            <form onSubmit={handleSubmit} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs text-slate-500 mb-1">部屋番号 *</label>
                <input
                  name="roomNumber"
                  required
                  placeholder="101"
                  autoFocus
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-lg font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
                >
                  {isPending ? "追加中..." : "追加"}
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="flex-1 border border-slate-200 rounded-lg py-2 hover:bg-slate-50 transition-colors"
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
