"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteOwner } from "@/app/actions";

export function DeleteOwnerButton({ ownerId, ownerName }: { ownerId: string; ownerName: string }) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleDelete() {
    if (!confirm(`オーナー「${ownerName}」を削除しますか？\n（所有物件は残り、オーナー割当だけ外れます）`)) return;
    startTransition(async () => {
      await deleteOwner(ownerId);
      router.push("/owners");
    });
  }

  return (
    <button onClick={handleDelete} disabled={isPending} className="text-sm border border-red-200 text-red-600 px-3 py-1.5 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors">
      {isPending ? "削除中..." : "削除"}
    </button>
  );
}
