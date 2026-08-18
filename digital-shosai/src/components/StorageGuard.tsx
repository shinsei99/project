"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { probeStorage, requestPersistence } from "@/lib/db";
import type { StorageState } from "@/lib/types";

/**
 * 起動時に「本当に保存できるか」を1KB書いて確かめ、駄目なら理由を出す。
 *
 * **無言で失敗させないために置いている。** Safari のプライベートタブでは
 * IndexedDB の書き込みがエラー内容 null のまま失敗し、上限も 1000MB と小さく申告される
 * （2026-08-17・iPhone実機で確認）。以前は取り込みが静かに失敗するだけで、
 * 原因が分からない状態だった。
 */
export function StorageGuard() {
  const [state, setState] = useState<StorageState | null>(null);

  useEffect(() => {
    let alive = true;
    probeStorage().then((s) => {
      if (!alive) return;
      setState(s);
      // 書けるなら「勝手に消さないで」と頼んでおく（対応環境のみ）
      if (s.writable) requestPersistence();
    });
    return () => {
      alive = false;
    };
  }, []);

  if (!state || state.writable) return null;

  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-2 rounded-xl border border-amber-600 bg-amber-950/40 px-4 py-3 text-sm text-amber-200"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="space-y-1">
        <p className="font-semibold">この状態では本を保存できません</p>
        <p className="text-amber-200/90">{state.reason}</p>
      </div>
    </div>
  );
}
