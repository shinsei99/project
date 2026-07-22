"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { putAudio, getAudio, deleteAudio } from "@/lib/audioStore";

/* ---------- 型 ---------- */
type Task = { summary: string; nextAction: string; id: string };
/** 録音した元音声への参照。本体は IndexedDB(bd_audio) に id で保存。 */
type AudioClip = { id: string; sec: number; mimeType: string };
type AnalyzeResult = {
  title: string;
  tasks: Task[];
  ideas: string[];
  business: string[];
  others: string[];
};
type Detail = { label: string; value: string };
type ImageResult = {
  title: string;
  summary: string[];
  details?: Detail[];
  nextAction: string;
};

/** tasksOnly=true は「メモは削除済みだがタスクだけ残す」状態（メモ一覧・履歴には出さない）。 */
type TextEntry = { id: string; ts: number; kind: "text"; input: string; result: AnalyzeResult; audio?: AudioClip[]; tasksOnly?: boolean };
type ImageEntry = {
  id: string;
  ts: number;
  kind: "image";
  result: ImageResult;
  count?: number;
  images?: string[];
};
type HistoryEntry = TextEntry | ImageEntry;

const ACCESS_KEY = "bd_access_code";
const HISTORY_KEY = "bd_history";
const TASK_ORDER_KEY = "bd_task_order";
const HISTORY_MAX = 200;
const MAX_IMAGES = 10;
const MAX_REC_SEC = 900; // 録音の上限（15分）。Vercelの本文サイズ/実行時間制限の保険
const MAX_AUDIO_BYTES = 3.5 * 1024 * 1024; // 送信音声の上限（base64化後もVercel本文上限に収める）

/* ---------- 履歴保存（localStorageのみ。容量超過時は古い写真→古い項目を間引く） ---------- */
/* 旧フォーマット（感情ログ/ideasがオブジェクト/titleなし）を新形式へ変換 */
function toStr(x: unknown): string {
  if (typeof x === "string") return x;
  if (x && typeof x === "object" && "content" in x) return String((x as { content: unknown }).content ?? "");
  return "";
}
function normalize(e: HistoryEntry): HistoryEntry {
  if (e.kind === "text") {
    const r = (e.result ?? {}) as Record<string, unknown>;
    const arr = (v: unknown) => (Array.isArray(v) ? v.map(toStr).filter(Boolean) : []);
    const emotions = arr(r.emotions);
    return {
      ...e,
      result: {
        title: (typeof r.title === "string" && r.title) || (e.input ? e.input.slice(0, 24) : "メモ"),
        tasks: Array.isArray(r.tasks)
          ? (r.tasks as Task[]).map((t) => ({ ...t, id: t.id || newId() })) // 並べ替え用に安定IDを付与
          : [],
        ideas: arr(r.ideas),
        business: arr(r.business),
        others: Array.isArray(r.others) ? arr(r.others) : emotions, // 旧emotionsはその他へ
      },
    };
  }
  return e;
}
function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const list = raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
    return list.map(normalize);
  } catch {
    return [];
  }
}
function stripImages(e: HistoryEntry): HistoryEntry {
  return e.kind === "image" ? { ...e, images: undefined } : e;
}
function persistHistory(list: HistoryEntry[]) {
  const base = list.slice(0, HISTORY_MAX);
  const variants: HistoryEntry[][] = [
    base,
    base.map((e, i) => (i >= 6 ? stripImages(e) : e)),
    base.map((e) => stripImages(e)),
    base.slice(0, 50).map((e) => stripImages(e)),
  ];
  for (const v of variants) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(v));
      return;
    } catch {
      /* 次の縮小案へ */
    }
  }
}
function newId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}
function formatDate(ts: number): string {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function fmtDuration(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}
/** 文字列配列を trim して空行を除く（編集の保存時に使う）。 */
function cleanArr(a: string[]): string[] {
  return a.map((s) => s.trim()).filter(Boolean);
}
function entryText(e: HistoryEntry): string {
  if (e.kind === "text") {
    return [
      e.result.title,
      e.input,
      ...e.result.tasks.flatMap((t) => [t.summary, t.nextAction]),
      ...e.result.ideas,
      ...e.result.business,
      ...e.result.others,
    ].join(" ");
  }
  return [
    e.result.title,
    ...e.result.summary,
    ...(e.result.details ?? []).flatMap((d) => [d.label, d.value]),
    e.result.nextAction,
  ].join(" ");
}

/* ---------- 画像をクライアント側で縮小して dataURL 化 ---------- */
async function fileToCompressedDataURL(file: File, maxSize = 1100, quality = 0.62): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = reject;
    im.src = dataUrl;
  });
  const scale = Math.min(1, maxSize / Math.max(img.width, img.height));
  const w = Math.round(img.width * scale);
  const h = Math.round(img.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return dataUrl;
  ctx.drawImage(img, 0, 0, w, h);
  return canvas.toDataURL("image/jpeg", quality);
}

/* ---------- 長押しドラッグで並べ替えできるリスト ---------- */
function ReorderList({
  keys,
  onReorder,
  renderRow,
  className = "flex flex-col gap-2",
}: {
  keys: string[];
  onReorder: (next: string[]) => void;
  renderRow: (key: string) => React.ReactNode;
  className?: string;
}) {
  const [order, setOrder] = useState<string[]>(keys);
  const orderRef = useRef<string[]>(keys);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const lpTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startPt = useRef<{ x: number; y: number } | null>(null);
  const dragging = useRef(false);
  const moved = useRef(false);
  const justDragged = useRef(false);

  useEffect(() => {
    orderRef.current = order;
  }, [order]);
  // 親の並び（追加・削除・整理結果）をドラッグ中でなければ取り込む
  useEffect(() => {
    if (!dragging.current) setOrder(keys);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keys.join("|")]);

  function clearLP() {
    if (lpTimer.current) {
      clearTimeout(lpTimer.current);
      lpTimer.current = null;
    }
  }
  function onDown(e: React.PointerEvent, key: string) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    // 入力・ボタン等の操作中はドラッグを開始しない
    if ((e.target as HTMLElement).closest("input,textarea,button,select,audio,a,[contenteditable]")) return;
    startPt.current = { x: e.clientX, y: e.clientY };
    moved.current = false;
    const el = e.currentTarget as HTMLElement;
    const pid = e.pointerId;
    clearLP();
    lpTimer.current = setTimeout(() => {
      dragging.current = true;
      setDragKey(key);
      try {
        el.setPointerCapture(pid);
      } catch {
        /* 無視 */
      }
      if (typeof navigator !== "undefined" && "vibrate" in navigator) {
        try {
          navigator.vibrate?.(12);
        } catch {
          /* 無視 */
        }
      }
    }, 320);
  }
  function onMove(e: React.PointerEvent) {
    if (!dragging.current) {
      const sp = startPt.current;
      if (sp && Math.hypot(e.clientX - sp.x, e.clientY - sp.y) > 8) clearLP(); // 動いたら長押し不成立
      return;
    }
    e.preventDefault();
    moved.current = true;
    const under = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null;
    const row = under?.closest("[data-rk]") as HTMLElement | null;
    const overKey = row?.getAttribute("data-rk");
    if (!overKey || overKey === dragKey) return;
    setOrder((prev) => {
      const from = prev.indexOf(dragKey!);
      const to = prev.indexOf(overKey);
      if (from < 0 || to < 0 || from === to) return prev;
      const next = prev.slice();
      const [it] = next.splice(from, 1);
      next.splice(to, 0, it);
      return next;
    });
  }
  function onUp(e: React.PointerEvent) {
    clearLP();
    startPt.current = null;
    if (dragging.current) {
      dragging.current = false;
      setDragKey(null);
      if (moved.current) {
        justDragged.current = true;
        e.preventDefault();
        onReorder(orderRef.current);
        setTimeout(() => {
          justDragged.current = false;
        }, 0);
      }
    }
  }

  return (
    <div className={className}>
      {order.map((key) => (
        <div
          key={key}
          data-rk={key}
          onPointerDown={(e) => onDown(e, key)}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onClickCapture={(e) => {
            if (justDragged.current) {
              e.preventDefault();
              e.stopPropagation();
            }
          }}
          className={dragKey === key ? "scale-[0.99] opacity-60" : ""}
          style={{
            touchAction: dragKey ? "none" : "pan-y",
            WebkitTouchCallout: "none",
            WebkitUserSelect: dragKey ? "none" : "auto",
          }}
        >
          {renderRow(key)}
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const [code, setCode] = useState("");
  const [authed, setAuthed] = useState(false);
  const [view, setView] = useState<"home" | "history">("home");

  const [text, setText] = useState("");
  const [loadingText, setLoadingText] = useState(false);

  // 音声録音 → 文字起こし
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef(0); // 停止時の録音秒数を確実に取るための実値
  // 整理(analyze)されるまで音声を一時保持し、作られたメモに元データとして紐付ける
  const pendingAudioRef = useRef<{ blob: Blob; sec: number }[]>([]);

  const [previews, setPreviews] = useState<string[]>([]);
  const [loadingImage, setLoadingImage] = useState(false);
  const fileCamRef = useRef<HTMLInputElement>(null);
  const fileLibRef = useRef<HTMLInputElement>(null);

  // 無音カメラ（アプリ内カメラ：OSのシャッター音が鳴らない）
  const [camOpen, setCamOpen] = useState(false);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [flash, setFlash] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const camStreamRef = useRef<MediaStream | null>(null);

  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [taskOrder, setTaskOrder] = useState<string[]>([]); // タスクの手動並べ替え順（task.id）
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(ACCESS_KEY);
    if (saved) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCode(saved);
      setAuthed(true);
    }
    setHistory(loadHistory());
    try {
      const raw = localStorage.getItem(TASK_ORDER_KEY);
      if (raw) setTaskOrder(JSON.parse(raw) as string[]);
    } catch {
      /* 無視 */
    }
  }, []);

  // 画面を離れる時に録音タイマー・マイクを確実に止める
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // 無音カメラ：開いている間だけカメラ映像を流す（facing切替で入れ直し）
  useEffect(() => {
    if (!camOpen) return;
    let cancelled = false;
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 2560 }, height: { ideal: 1440 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        camStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
      } catch (err) {
        if (cancelled) return;
        const name = err instanceof DOMException ? err.name : "";
        setError(
          name === "NotAllowedError" || name === "SecurityError"
            ? "カメラの使用が許可されていません（ブラウザ／端末の設定で許可してください）"
            : "カメラを起動できませんでした"
        );
        setCamOpen(false);
      }
    })();
    return () => {
      cancelled = true;
      camStreamRef.current?.getTracks().forEach((t) => t.stop());
      camStreamRef.current = null;
    };
  }, [camOpen, facing]);

  const textEntries = useMemo(
    () => history.filter((e): e is TextEntry => e.kind === "text"),
    [history]
  );
  // メモ一覧に出すのは「メモ本文が残っている」もの（タスクだけ残した削除済みは除外）
  const memoEntries = useMemo(() => textEntries.filter((e) => !e.tasksOnly), [textEntries]);
  // 履歴カウント（tasksOnlyの削除済みメモは数えない）
  const historyCount = useMemo(
    () => history.filter((e) => !(e.kind === "text" && e.tasksOnly)).length,
    [history]
  );
  const imageEntries = useMemo(
    () => history.filter((e): e is ImageEntry => e.kind === "image"),
    [history]
  );
  // 全タスクを集約（トップに常時表示）
  const taskItems = useMemo(() => {
    const out: { entryId: string; idx: number; task: Task; ts: number }[] = [];
    for (const e of textEntries) e.result.tasks.forEach((task, idx) => out.push({ entryId: e.id, idx, task, ts: e.ts }));
    return out;
  }, [textEntries]);
  // 手動並べ替え順を反映（未登録＝新規タスクは先頭に自然順で置く）
  const orderedTaskItems = useMemo(() => {
    const pos = new Map(taskOrder.map((id, i) => [id, i]));
    const known = taskItems.filter((t) => pos.has(t.task.id));
    const unknown = taskItems.filter((t) => !pos.has(t.task.id));
    known.sort((a, b) => pos.get(a.task.id)! - pos.get(b.task.id)!);
    return [...unknown, ...known];
  }, [taskItems, taskOrder]);

  function authHeaders(): HeadersInit {
    return { "Content-Type": "application/json", "x-access-code": code };
  }
  function login(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    localStorage.setItem(ACCESS_KEY, code.trim());
    setAuthed(true);
    setError(null);
  }
  function logout() {
    localStorage.removeItem(ACCESS_KEY);
    setAuthed(false);
    setCode("");
    setPreviews([]);
    pendingAudioRef.current = []; // 未紐付けの録音は破棄
    setCamOpen(false); // カメラが開いていれば閉じる
  }

  /* ---------- 履歴操作 ---------- */
  function addEntry(entry: HistoryEntry) {
    setHistory((prev) => {
      const next = [entry, ...prev].slice(0, HISTORY_MAX);
      persistHistory(next);
      return next;
    });
  }
  function deleteEntry(id: string) {
    const target = history.find((e) => e.id === id);
    // メモに紐付く元音声はどちらの場合も削除
    if (target?.kind === "text" && target.audio?.length) {
      void deleteAudio(target.audio.map((a) => a.id));
    }
    // タスクを持つメモは、メモ本文だけ消してタスクは残す（tasksOnly化）
    if (target?.kind === "text" && target.result.tasks.length > 0) {
      setHistory((prev) => {
        const next = prev.map((e) =>
          e.id === id && e.kind === "text"
            ? { ...e, tasksOnly: true, audio: undefined, result: { ...e.result, ideas: [], business: [], others: [] } }
            : e
        );
        persistHistory(next);
        return next;
      });
      return;
    }
    // それ以外（タスクなしメモ・写真スクラップ）は従来どおり完全削除
    setHistory((prev) => {
      const next = prev.filter((e) => e.id !== id);
      persistHistory(next);
      return next;
    });
  }
  function clearAll() {
    if (!confirm("すべての履歴を削除しますか？（この端末から消えます。タスク・録音も消えます）")) return;
    const audioIds = history.flatMap((e) =>
      e.kind === "text" && e.audio ? e.audio.map((a) => a.id) : []
    );
    if (audioIds.length) void deleteAudio(audioIds);
    setHistory([]);
    persistHistory([]);
  }
  // 並べ替え：指定 kind のエントリだけを新しい順序で元の位置に並べ直す
  function reorderEntries(ids: string[], isTarget: (e: HistoryEntry) => boolean) {
    setHistory((prev) => {
      const byId = new Map(prev.map((e) => [e.id, e]));
      const reordered = ids.map((id) => byId.get(id)).filter((e): e is HistoryEntry => !!e);
      const slots: number[] = [];
      prev.forEach((e, i) => {
        if (isTarget(e)) slots.push(i);
      });
      const next = prev.slice();
      slots.forEach((pos, i) => {
        if (reordered[i]) next[pos] = reordered[i];
      });
      persistHistory(next);
      return next;
    });
  }
  function reorderMemos(ids: string[]) {
    reorderEntries(ids, (e) => e.kind === "text" && !e.tasksOnly);
  }
  function reorderScraps(ids: string[]) {
    reorderEntries(ids, (e) => e.kind === "image");
  }
  function reorderTasks(ids: string[]) {
    setTaskOrder(ids);
    try {
      localStorage.setItem(TASK_ORDER_KEY, JSON.stringify(ids));
    } catch {
      /* 無視 */
    }
  }

  // メモ（テキスト項目）の本文を編集・保存
  function saveMemo(id: string, result: AnalyzeResult) {
    setHistory((prev) => {
      const next = prev.map((e) => (e.id === id && e.kind === "text" ? { ...e, result } : e));
      persistHistory(next);
      return next;
    });
  }
  // 写真スクラップの本文を編集・保存
  function saveScrap(id: string, result: ImageResult) {
    setHistory((prev) => {
      const next = prev.map((e) => (e.id === id && e.kind === "image" ? { ...e, result } : e));
      persistHistory(next);
      return next;
    });
  }
  function setEntryTasks(id: string, tasks: Task[]) {
    setHistory((prev) => {
      const mapped = prev.map((e) =>
        e.id === id && e.kind === "text" ? { ...e, result: { ...e.result, tasks } } : e
      );
      // メモ削除済み(tasksOnly)でタスクも全部消えたエントリは掃除する
      const next = mapped.filter((e) => !(e.kind === "text" && e.tasksOnly && e.result.tasks.length === 0));
      persistHistory(next);
      return next;
    });
  }
  function updateTask(entryId: string, idx: number, t: Task) {
    const e = history.find((h) => h.id === entryId);
    if (!e || e.kind !== "text") return;
    setEntryTasks(entryId, e.result.tasks.map((x, i) => (i === idx ? t : x)));
  }
  function deleteTask(entryId: string, idx: number) {
    const e = history.find((h) => h.id === entryId);
    if (!e || e.kind !== "text") return;
    setEntryTasks(entryId, e.result.tasks.filter((_, i) => i !== idx));
  }

  async function analyzeText() {
    if (!text.trim()) return;
    setLoadingText(true);
    setError(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "解析に失敗しました");
      // タスクに安定IDを付与（並べ替え用）
      if (Array.isArray(data?.tasks)) {
        data.tasks = data.tasks.map((t: Task) => ({ ...t, id: newId() }));
      }
      // 保留中の録音を IndexedDB に保存し、このメモへ元データとして紐付ける
      const clips: AudioClip[] = [];
      const pending = pendingAudioRef.current;
      pendingAudioRef.current = [];
      for (const p of pending) {
        try {
          const aid = newId();
          await putAudio(aid, await p.blob.arrayBuffer());
          clips.push({ id: aid, sec: p.sec, mimeType: p.blob.type || "audio/webm" });
        } catch {
          /* 音声保存に失敗してもメモ本体は残す */
        }
      }
      addEntry({
        id: newId(),
        ts: Date.now(),
        kind: "text",
        input: text.trim(),
        result: data,
        audio: clips.length ? clips : undefined,
      });
      setText(""); // 反映されたら入力欄を白紙に
    } catch (err) {
      setError(err instanceof Error ? err.message : "解析に失敗しました");
    } finally {
      setLoadingText(false);
    }
  }

  /* ---------- 音声録音 → 文字起こし ---------- */
  function stopTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }
  function cleanupStream() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }
  function pickAudioMime(): string {
    if (typeof MediaRecorder === "undefined") return "";
    // mp4(AAC)＝iOS Safari / webm(opus)＝Chrome・Android を優先
    const cands = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
    for (const c of cands) {
      try {
        if (MediaRecorder.isTypeSupported(c)) return c;
      } catch {
        /* 次の候補へ */
      }
    }
    return "";
  }
  function blobToDataURL(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result as string);
      r.onerror = reject;
      r.readAsDataURL(blob);
    });
  }
  async function startRecording() {
    setError(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("このブラウザは録音に対応していません");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickAudioMime();
      const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        void finishRecording();
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
      setElapsed(0);
      elapsedRef.current = 0;
      timerRef.current = setInterval(() => {
        setElapsed((s) => {
          const next = s + 1;
          elapsedRef.current = next;
          if (next >= MAX_REC_SEC) stopRecording();
          return next;
        });
      }, 1000);
    } catch (err) {
      cleanupStream();
      const name = err instanceof DOMException ? err.name : "";
      setError(
        name === "NotAllowedError" || name === "SecurityError"
          ? "マイクの使用が許可されていません（ブラウザ／端末の設定で許可してください）"
          : "録音を開始できませんでした"
      );
    }
  }

  function stopRecording() {
    stopTimer();
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop(); // → onstop → finishRecording
    setRecording(false);
  }

  async function finishRecording() {
    cleanupStream();
    const rec = recorderRef.current;
    const type = rec?.mimeType || chunksRef.current[0]?.type || "audio/webm";
    const blob = new Blob(chunksRef.current, { type });
    chunksRef.current = [];
    recorderRef.current = null;
    if (blob.size === 0) {
      setError("録音が空でした。もう一度お試しください。");
      return;
    }
    if (blob.size > MAX_AUDIO_BYTES) {
      setError("録音が長すぎます。10分以内を目安に短く録り直してください。");
      return;
    }
    setTranscribing(true);
    setError(null);
    try {
      const dataUrl = await blobToDataURL(blob);
      const res = await fetch("/api/transcribe", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ audio: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "文字起こしに失敗しました");
      const t = (typeof data?.text === "string" ? data.text : "").trim();
      if (!t) {
        setError("音声から文字を認識できませんでした。");
        return;
      }
      // 元音声を一時保持（次に「整理」して作られるメモに紐付ける）
      pendingAudioRef.current.push({ blob, sec: elapsedRef.current });
      // 既存の入力があれば改行して追記（複数回の録音・手入力と併用できる）
      setText((prev) => (prev.trim() ? `${prev.replace(/\s*$/, "")}\n${t}` : t));
    } catch (err) {
      setError(err instanceof Error ? err.message : "文字起こしに失敗しました");
    } finally {
      setTranscribing(false);
    }
  }

  /* ---------- 無音カメラ（アプリ内カメラでシャッター音なし撮影） ---------- */
  function openSilentCamera() {
    setError(null);
    if (previews.length >= MAX_IMAGES) {
      setError(`画像は最大${MAX_IMAGES}枚までです`);
      return;
    }
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("このブラウザはカメラに対応していません");
      return;
    }
    setCamOpen(true); // 実際のストリーム開始は useEffect で
  }
  function closeSilentCamera() {
    setCamOpen(false); // useEffect のクリーンアップでストリーム停止
  }
  function captureSilent() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    if (previews.length >= MAX_IMAGES) {
      setError(`画像は最大${MAX_IMAGES}枚までです`);
      return;
    }
    // 既存の写真と同じ圧縮基準（長辺1100px / JPEG品質0.62）で取り込む
    const maxSize = 1100;
    const quality = 0.62;
    const scale = Math.min(1, maxSize / Math.max(video.videoWidth, video.videoHeight));
    const w = Math.round(video.videoWidth * scale);
    const h = Math.round(video.videoHeight * scale);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, w, h);
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    setPreviews((prev) => [...prev, dataUrl].slice(0, MAX_IMAGES));
    // 音の代わりに一瞬フラッシュして撮れたことを知らせる
    setFlash(true);
    setTimeout(() => setFlash(false), 130);
  }

  async function onPickImages(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;
    setError(null);
    const room = MAX_IMAGES - previews.length;
    if (room <= 0) {
      setError(`画像は最大${MAX_IMAGES}枚までです`);
      return;
    }
    try {
      const compressed = await Promise.all(files.slice(0, room).map((f) => fileToCompressedDataURL(f)));
      setPreviews((prev) => [...prev, ...compressed].slice(0, MAX_IMAGES));
      if (files.length > room) setError(`${MAX_IMAGES}枚を超えた分は追加されませんでした`);
    } catch {
      setError("画像の読み込みに失敗しました");
    }
  }
  function removePreview(idx: number) {
    setPreviews((prev) => prev.filter((_, i) => i !== idx));
  }

  async function analyzeImages() {
    if (previews.length === 0) return;
    setLoadingImage(true);
    setError(null);
    try {
      const res = await fetch("/api/analyze-image", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ images: previews }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "解析に失敗しました");
      addEntry({ id: newId(), ts: Date.now(), kind: "image", result: data, count: previews.length, images: previews });
      setPreviews([]); // 反映されたら選択写真をクリア
    } catch (err) {
      setError(err instanceof Error ? err.message : "解析に失敗しました");
    } finally {
      setLoadingImage(false);
    }
  }

  /* ---------- ログイン画面 ---------- */
  if (!authed) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center gap-6 px-6">
        <div className="text-center">
          <div className="text-5xl">🧠</div>
          <h1 className="mt-3 text-xl font-bold">Brain Dump</h1>
          <p className="mt-1 text-sm text-zinc-400">頭の中を空っぽにして、AIに整理してもらう</p>
        </div>
        <form onSubmit={login} className="flex w-full flex-col gap-3">
          <input
            type="password"
            inputMode="text"
            autoComplete="off"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="アクセスコード"
            className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-center text-lg tracking-widest outline-none focus:border-indigo-500"
          />
          <button type="submit" className="w-full rounded-xl bg-indigo-600 py-3 font-semibold active:scale-[0.98]">
            はじめる
          </button>
          <p className="text-center text-xs text-zinc-600">一度入れれば次回から自動でログインします</p>
        </form>
      </main>
    );
  }

  /* ---------- ダッシュボード ---------- */
  return (
    <main className="mx-auto w-full max-w-md px-4 pb-24 pt-6">
      <header className="mb-5 flex items-center justify-between">
        <h1 className="text-lg font-bold">🧠 Brain Dump</h1>
        <div className="flex items-center gap-3">
          <button onClick={() => setView(view === "home" ? "history" : "home")} className="text-xs text-zinc-400 active:text-zinc-200">
            {view === "home" ? `🕘 履歴${historyCount ? `(${historyCount})` : ""}` : "← もどる"}
          </button>
          <button
            onClick={() => {
              if (confirm("ロックしますか？（もう一度アクセスコードが必要になります）")) logout();
            }}
            className="text-xs text-zinc-500 active:text-zinc-300"
          >
            ロック
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      {view === "history" ? (
        <HistoryView
          history={history}
          onDelete={deleteEntry}
          onClear={clearAll}
          onViewImage={setLightbox}
          onSaveMemo={saveMemo}
          onSaveScrap={saveScrap}
        />
      ) : (
        <>
          {/* 入力 */}
          <section className="mb-6">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder="今、頭の中にあることを全部ここに殴り書き…"
              className="w-full resize-none rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-[15px] leading-relaxed outline-none focus:border-indigo-500"
            />

            {/* 入力ボタン1行：録音 / 撮影 / 撮影S / フォト */}
            <input ref={fileCamRef} type="file" accept="image/*" capture="environment" onChange={onPickImages} className="hidden" />
            <input ref={fileLibRef} type="file" accept="image/*" multiple onChange={onPickImages} className="hidden" />
            <div className="mt-2 grid grid-cols-4 gap-2">
              {recording ? (
                <button
                  onClick={stopRecording}
                  className="flex flex-col items-center justify-center gap-0.5 rounded-2xl bg-red-600 py-2.5 text-[11px] font-semibold active:scale-[0.98]"
                >
                  <span className="text-lg leading-none">⏹</span>
                  {fmtDuration(elapsed)}
                </button>
              ) : (
                <button
                  onClick={startRecording}
                  disabled={transcribing || loadingText}
                  className="flex flex-col items-center justify-center gap-0.5 rounded-2xl border border-zinc-700 bg-zinc-900/60 py-2.5 text-[11px] text-zinc-200 disabled:opacity-40 active:scale-[0.98]"
                >
                  <span className="text-lg leading-none">{transcribing ? "⏳" : "🎙️"}</span>
                  {transcribing ? "変換中" : "録音"}
                </button>
              )}
              <button
                onClick={() => fileCamRef.current?.click()}
                disabled={previews.length >= MAX_IMAGES}
                className="flex flex-col items-center justify-center gap-0.5 rounded-2xl border border-zinc-700 bg-zinc-900/60 py-2.5 text-[11px] text-zinc-200 disabled:opacity-40 active:scale-[0.98]"
              >
                <span className="text-lg leading-none">📷</span>
                撮影
              </button>
              <button
                onClick={openSilentCamera}
                disabled={previews.length >= MAX_IMAGES}
                className="flex flex-col items-center justify-center gap-0.5 rounded-2xl border border-zinc-700 bg-zinc-900/60 py-2.5 text-[11px] text-zinc-200 disabled:opacity-40 active:scale-[0.98]"
              >
                <span className="text-lg leading-none">🔇</span>
                撮影S
              </button>
              <button
                onClick={() => fileLibRef.current?.click()}
                disabled={previews.length >= MAX_IMAGES}
                className="flex flex-col items-center justify-center gap-0.5 rounded-2xl border border-zinc-700 bg-zinc-900/60 py-2.5 text-[11px] text-zinc-200 disabled:opacity-40 active:scale-[0.98]"
              >
                <span className="text-lg leading-none">🖼</span>
                フォト
              </button>
            </div>

            <button
              onClick={analyzeText}
              disabled={loadingText || recording || transcribing || !text.trim()}
              className="mt-3 w-full rounded-2xl bg-indigo-600 py-3.5 font-semibold disabled:opacity-40 active:scale-[0.98]"
            >
              {loadingText ? "整理中…" : "🧹 脳を空っぽにする"}
            </button>

            {/* 選択した写真のプレビュー＋まとめて解析 */}
            {previews.length > 0 && (
              <div className="mt-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs text-zinc-500">{previews.length} / {MAX_IMAGES}枚</span>
                  <button onClick={() => setPreviews([])} className="text-xs text-zinc-500 active:text-red-400">クリア</button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {previews.map((src, i) => (
                    <div key={i} className="relative">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt={`page ${i + 1}`} onClick={() => setLightbox(src)} className="aspect-square w-full rounded-lg object-cover" />
                      <button onClick={() => removePreview(i)} className="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-zinc-800 text-xs text-zinc-200 ring-1 ring-zinc-600 active:bg-red-600" aria-label="削除">
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <button onClick={analyzeImages} disabled={loadingImage} className="mt-3 w-full rounded-2xl bg-emerald-600 py-3.5 font-semibold disabled:opacity-40 active:scale-[0.98]">
                  {loadingImage ? "読み取り中…" : `🔎 ${previews.length}枚をまとめて解析する`}
                </button>
              </div>
            )}
          </section>

          {/* タスク（全件トップに常時表示・編集削除可） */}
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-semibold text-zinc-300">📋 タスク<span className="ml-1 text-[11px] font-normal text-zinc-600">（長押しで並べ替え）</span></h2>
            <TaskMaster items={orderedTaskItems} onUpdate={updateTask} onDelete={deleteTask} onReorder={reorderTasks} />
          </section>

          {/* メモ（タイトルのみ・タップで詳細） */}
          {memoEntries.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-zinc-300">📝 メモ<span className="ml-1 text-[11px] font-normal text-zinc-600">（長押しで並べ替え）</span></h2>
              <ReorderList
                keys={memoEntries.map((e) => e.id)}
                onReorder={reorderMemos}
                renderRow={(id) => {
                  const e = memoEntries.find((m) => m.id === id);
                  return e ? <MemoRow entry={e} onDelete={deleteEntry} onSave={saveMemo} /> : null;
                }}
              />
            </section>
          )}

          {/* 写真スクラップ（結果一覧） */}
          {imageEntries.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-zinc-300">📷 写真スクラップ<span className="ml-1 text-[11px] font-normal text-zinc-600">（長押しで並べ替え）</span></h2>
              <ReorderList
                keys={imageEntries.map((e) => e.id)}
                onReorder={reorderScraps}
                renderRow={(id) => {
                  const e = imageEntries.find((m) => m.id === id);
                  return e ? <ScrapRow entry={e} onViewImage={setLightbox} onDelete={deleteEntry} onSave={saveScrap} /> : null;
                }}
              />
            </section>
          )}
        </>
      )}

      {/* 元写真の拡大表示 */}
      {lightbox && (
        <div onClick={() => setLightbox(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={lightbox} alt="原本" className="max-h-full max-w-full rounded-lg object-contain" />
          <span className="absolute right-4 top-4 text-sm text-zinc-400">タップで閉じる ✕</span>
        </div>
      )}

      {/* 無音カメラ（アプリ内カメラ・シャッター音なし） */}
      {camOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black">
          <video ref={videoRef} autoPlay playsInline muted className="min-h-0 w-full flex-1 object-contain" />

          {/* 撮影時の白フラッシュ（音の代わり） */}
          {flash && <div className="pointer-events-none absolute inset-0 bg-white transition-opacity" />}

          {/* 上部：閉じる・枚数・カメラ切替 */}
          <button
            onClick={closeSilentCamera}
            className="absolute left-4 top-5 flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-lg text-white active:bg-black/70"
            aria-label="閉じる"
          >
            ✕
          </button>
          <span className="absolute left-1/2 top-6 -translate-x-1/2 text-sm text-white/90">
            {previews.length} / {MAX_IMAGES}枚
          </span>
          <button
            onClick={() => setFacing((f) => (f === "environment" ? "user" : "environment"))}
            className="absolute right-4 top-5 flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-lg active:bg-black/70"
            aria-label="カメラ切替"
          >
            🔄
          </button>

          {/* 下部：シャッター・完了 */}
          <div className="relative flex items-center justify-center bg-black py-6">
            <button
              onClick={captureSilent}
              disabled={previews.length >= MAX_IMAGES}
              aria-label="撮影（無音）"
              className="h-[68px] w-[68px] rounded-full border-[5px] border-white bg-white/25 active:bg-white/50 disabled:opacity-40"
            />
            <button
              onClick={closeSilentCamera}
              className="absolute right-6 rounded-xl bg-white/15 px-4 py-2 text-sm text-white active:bg-white/30"
            >
              完了{previews.length ? `（${previews.length}）` : ""}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

/* ---------- 履歴ビュー（検索つき・詳細はここ） ---------- */
function HistoryView({
  history,
  onDelete,
  onClear,
  onViewImage,
  onSaveMemo,
  onSaveScrap,
}: {
  history: HistoryEntry[];
  onDelete: (id: string) => void;
  onClear: () => void;
  onViewImage: (src: string) => void;
  onSaveMemo: (id: string, result: AnalyzeResult) => void;
  onSaveScrap: (id: string, result: ImageResult) => void;
}) {
  const [query, setQuery] = useState("");
  // タスクだけ残した削除済みメモ(tasksOnly)は履歴には出さない
  const visible = history.filter((e) => !(e.kind === "text" && e.tasksOnly));
  if (visible.length === 0) {
    return <div className="mt-16 text-center text-sm text-zinc-600">まだ履歴はありません。<br />整理すると、ここに保存されます。</div>;
  }
  const q = query.trim().toLowerCase();
  const filtered = q ? visible.filter((e) => entryText(e).toLowerCase().includes(q)) : visible;
  return (
    <div className="flex flex-col gap-2">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="🔍 履歴を検索（キーワード）"
        className="w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-indigo-500"
      />
      <div className="mb-1 flex items-center justify-between">
        <p className="text-xs text-zinc-500">{q ? `${filtered.length} / ${visible.length}件` : `${visible.length}件`}</p>
        <button onClick={onClear} className="text-xs text-red-400 active:text-red-300">すべて消去</button>
      </div>
      {filtered.length === 0 ? (
        <p className="mt-8 text-center text-sm text-zinc-600">「{query}」に一致する履歴はありません</p>
      ) : (
        filtered.map((e) =>
          e.kind === "text" ? (
            <MemoRow key={e.id} entry={e} onDelete={onDelete} onSave={onSaveMemo} />
          ) : (
            <ScrapRow key={e.id} entry={e} onViewImage={onViewImage} onDelete={onDelete} onSave={onSaveScrap} />
          )
        )
      )}
    </div>
  );
}

/* ---------- メモ行（タイトル＋タップで詳細） ---------- */
function MemoRow({
  entry,
  onDelete,
  onSave,
}: {
  entry: TextEntry;
  onDelete?: (id: string) => void;
  onSave?: (id: string, result: AnalyzeResult) => void;
}) {
  const r = entry.result;
  const title = r.title || entry.input.slice(0, 24) || "無題";
  const clips = entry.audio ?? [];
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<AnalyzeResult>(r);
  return (
    <details
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
      className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950/40"
    >
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 p-3">
        <span className="min-w-0 flex-1 truncate text-sm">
          📝 {title}
          {clips.length > 0 && <span className="ml-1 text-xs text-zinc-500">🎙️</span>}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-zinc-600">{formatDate(entry.ts)}</span>
          {onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (confirm("このメモを削除しますか？（録音があれば一緒に消えます）")) onDelete(entry.id);
              }}
              className="text-sm text-zinc-600 active:text-red-400"
              aria-label="このメモを削除"
            >
              🗑
            </button>
          )}
        </span>
      </summary>
      <div className="px-3 pb-3">
        {editing ? (
          <MemoEditor
            draft={draft}
            setDraft={setDraft}
            onCancel={() => setEditing(false)}
            onSave={() => {
              onSave?.(entry.id, {
                title: draft.title.trim(),
                tasks: draft.tasks,
                ideas: cleanArr(draft.ideas),
                business: cleanArr(draft.business),
                others: cleanArr(draft.others),
              });
              setEditing(false);
            }}
          />
        ) : (
          <>
            <MemoDetail result={r} />
            {onSave && (
              <button
                onClick={() => {
                  setDraft(r);
                  setEditing(true);
                }}
                className="mt-3 text-xs text-zinc-500 active:text-zinc-200"
              >
                ✏️ 文字を編集
              </button>
            )}
          </>
        )}
        {clips.length > 0 && open && <AudioClipsPlayer clips={clips} />}
      </div>
    </details>
  );
}

function MemoDetail({ result }: { result: AnalyzeResult }) {
  const groups = [
    { label: "💡 アイデア", items: result.ideas },
    { label: "💼 ビジネス", items: result.business },
    { label: "🗒 その他", items: result.others },
  ].filter((g) => g.items.length > 0);
  if (groups.length === 0) {
    return <p className="text-xs text-zinc-600">メモはありません（タスクのみ）</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      {groups.map((g) => (
        <div key={g.label}>
          <p className="mb-1 text-xs font-semibold text-zinc-400">{g.label}</p>
          <ul className="flex flex-col gap-1.5">
            {g.items.map((it, i) => (
              <li key={i} className="rounded-lg bg-zinc-900 p-2.5 text-sm">{it}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/* ---------- 編集用：文字列リスト（1項目=1入力・行の追加削除可） ---------- */
const EDIT_INPUT = "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm outline-none focus:border-indigo-500";

function EditList({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-zinc-400">{label}</p>
      <div className="flex flex-col gap-1.5">
        {items.map((it, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <textarea
              value={it}
              rows={1}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))}
              className={`${EDIT_INPUT} resize-none`}
            />
            <button
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="mt-1.5 shrink-0 text-zinc-500 active:text-red-400"
              aria-label="この行を削除"
            >
              🗑
            </button>
          </div>
        ))}
        <button
          onClick={() => onChange([...items, ""])}
          className="self-start text-xs text-zinc-500 active:text-zinc-200"
        >
          ＋ 行を追加
        </button>
      </div>
    </div>
  );
}

/* ---------- メモの本文編集フォーム ---------- */
function MemoEditor({
  draft,
  setDraft,
  onSave,
  onCancel,
}: {
  draft: AnalyzeResult;
  setDraft: (r: AnalyzeResult) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-xs font-semibold text-zinc-400">タイトル</p>
        <input
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          placeholder="タイトル"
          className={EDIT_INPUT}
        />
      </div>
      <EditList label="💡 アイデア" items={draft.ideas} onChange={(ideas) => setDraft({ ...draft, ideas })} />
      <EditList label="💼 ビジネス" items={draft.business} onChange={(business) => setDraft({ ...draft, business })} />
      <EditList label="🗒 その他" items={draft.others} onChange={(others) => setDraft({ ...draft, others })} />
      <p className="text-[11px] text-zinc-600">※ タスクは上の「📋 タスク」から編集できます</p>
      <div className="flex gap-2">
        <button onClick={onSave} className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold active:scale-95">
          保存
        </button>
        <button onClick={onCancel} className="rounded-lg bg-zinc-700 px-4 py-1.5 text-xs active:scale-95">
          キャンセル
        </button>
      </div>
    </div>
  );
}

/* ---------- 写真スクラップの本文編集フォーム ---------- */
function ScrapEditor({
  draft,
  setDraft,
  onSave,
  onCancel,
}: {
  draft: ImageResult;
  setDraft: (r: ImageResult) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const details = draft.details ?? [];
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-xs font-semibold text-zinc-400">タイトル</p>
        <input
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          placeholder="タイトル"
          className={EDIT_INPUT}
        />
      </div>

      <EditList label="📝 要点" items={draft.summary} onChange={(summary) => setDraft({ ...draft, summary })} />

      <div>
        <p className="mb-1 text-xs font-semibold text-zinc-400">📌 記録事項（項目名・内容）</p>
        <div className="flex flex-col gap-1.5">
          {details.map((d, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <input
                value={d.label}
                onChange={(e) =>
                  setDraft({ ...draft, details: details.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })
                }
                placeholder="項目名"
                className={`${EDIT_INPUT} w-1/3`}
              />
              <input
                value={d.value}
                onChange={(e) =>
                  setDraft({ ...draft, details: details.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)) })
                }
                placeholder="内容"
                className={EDIT_INPUT}
              />
              <button
                onClick={() => setDraft({ ...draft, details: details.filter((_, j) => j !== i) })}
                className="mt-1.5 shrink-0 text-zinc-500 active:text-red-400"
                aria-label="この行を削除"
              >
                🗑
              </button>
            </div>
          ))}
          <button
            onClick={() => setDraft({ ...draft, details: [...details, { label: "", value: "" }] })}
            className="self-start text-xs text-zinc-500 active:text-zinc-200"
          >
            ＋ 行を追加
          </button>
        </div>
      </div>

      <div>
        <p className="mb-1 text-xs font-semibold text-zinc-400">💪 次の行動</p>
        <textarea
          value={draft.nextAction}
          rows={2}
          onChange={(e) => setDraft({ ...draft, nextAction: e.target.value })}
          className={`${EDIT_INPUT} resize-none`}
        />
      </div>

      <div className="flex gap-2">
        <button onClick={onSave} className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold active:scale-95">
          保存
        </button>
        <button onClick={onCancel} className="rounded-lg bg-zinc-700 px-4 py-1.5 text-xs active:scale-95">
          キャンセル
        </button>
      </div>
    </div>
  );
}

/* ---------- 録音した元音声の再生（IndexedDBから読み出し） ---------- */
function AudioClipsPlayer({ clips }: { clips: AudioClip[] }) {
  // undefined=読み込み中 / string=再生URL / null=見つからず
  const [urls, setUrls] = useState<Record<string, string | null>>({});
  const createdRef = useRef<string[]>([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const out: Record<string, string | null> = {};
      for (const c of clips) {
        try {
          const buf = await getAudio(c.id);
          if (buf) {
            const url = URL.createObjectURL(new Blob([buf], { type: c.mimeType }));
            out[c.id] = url;
            createdRef.current.push(url);
          } else {
            out[c.id] = null;
          }
        } catch {
          out[c.id] = null;
        }
      }
      if (alive) setUrls(out);
    })();
    return () => {
      alive = false;
      createdRef.current.forEach((u) => URL.revokeObjectURL(u));
      createdRef.current = [];
    };
  }, [clips]);

  return (
    <div className="mt-3">
      <p className="mb-1.5 text-xs text-zinc-500">🎙️ 録音（元データ）</p>
      <div className="flex flex-col gap-2">
        {clips.map((c) => {
          const u = urls[c.id];
          return (
            <div key={c.id} className="rounded-lg bg-zinc-900 p-2">
              {u === undefined ? (
                <p className="px-1 py-1.5 text-xs text-zinc-600">読み込み中…</p>
              ) : u ? (
                <>
                  <audio controls preload="none" src={u} className="w-full" />
                  <p className="mt-1 px-1 text-[11px] text-zinc-600">長さ {fmtDuration(c.sec)}</p>
                </>
              ) : (
                <p className="px-1 py-1.5 text-xs text-zinc-600">
                  音声が見つかりません（この端末に保存されていません）
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- スクラップ行（タイトル＋タップで詳細・元写真） ---------- */
function ScrapRow({
  entry,
  onViewImage,
  onDelete,
  onSave,
}: {
  entry: ImageEntry;
  onViewImage: (src: string) => void;
  onDelete?: (id: string) => void;
  onSave?: (id: string, result: ImageResult) => void;
}) {
  const r = entry.result;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ImageResult>(r);
  return (
    <details className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950/40">
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 p-3">
        <span className="min-w-0 flex-1 truncate text-sm">
          📷 {r.title || "スクラップ"}
          {entry.count && entry.count > 1 ? `（${entry.count}枚）` : ""}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-zinc-600">{formatDate(entry.ts)}</span>
          {onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (confirm("このスクラップを削除しますか？")) onDelete(entry.id);
              }}
              className="text-sm text-zinc-600 active:text-red-400"
              aria-label="このスクラップを削除"
            >
              🗑
            </button>
          )}
        </span>
      </summary>
      <div className="px-3 pb-3">
        {editing ? (
          <ScrapEditor
            draft={draft}
            setDraft={setDraft}
            onCancel={() => setEditing(false)}
            onSave={() => {
              onSave?.(entry.id, {
                title: draft.title.trim(),
                summary: cleanArr(draft.summary),
                details: (draft.details ?? [])
                  .map((d) => ({ label: d.label.trim(), value: d.value.trim() }))
                  .filter((d) => d.label || d.value),
                nextAction: draft.nextAction.trim(),
              });
              setEditing(false);
            }}
          />
        ) : (
          <>
            {r.details && r.details.length > 0 && (
              <dl className="mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-lg bg-zinc-950/60 p-3 text-sm">
                {r.details.map((d, i) => (
                  <div key={i} className="contents">
                    <dt className="text-zinc-500">{d.label}</dt>
                    <dd className="font-medium text-zinc-100">{d.value}</dd>
                  </div>
                ))}
              </dl>
            )}
            <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-300">
              {r.summary.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <p className="mt-3 rounded-lg bg-emerald-950/50 p-3 text-sm text-emerald-300">💪 {r.nextAction}</p>
            {onSave && (
              <button
                onClick={() => {
                  setDraft(r);
                  setEditing(true);
                }}
                className="mt-3 text-xs text-zinc-500 active:text-zinc-200"
              >
                ✏️ 文字を編集
              </button>
            )}
          </>
        )}
        {entry.images && entry.images.length > 0 && (
          <div className="mt-3">
            <p className="mb-1.5 text-xs text-zinc-500">元の写真（タップで拡大）</p>
            <div className="grid grid-cols-4 gap-1.5">
              {entry.images.map((src, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={i} src={src} alt={`orig ${i + 1}`} onClick={() => onViewImage(src)} className="aspect-square w-full rounded-md object-cover" />
              ))}
            </div>
          </div>
        )}
      </div>
    </details>
  );
}

/* ---------- タスク一覧（集約・編集・削除） ---------- */
function TaskMaster({
  items,
  onUpdate,
  onDelete,
  onReorder,
}: {
  items: { entryId: string; idx: number; task: Task; ts: number }[];
  onUpdate: (entryId: string, idx: number, t: Task) => void;
  onDelete: (entryId: string, idx: number) => void;
  onReorder: (ids: string[]) => void;
}) {
  const [editId, setEditId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Task>({ summary: "", nextAction: "", id: "" });

  if (items.length === 0) {
    return <p className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4 text-xs text-zinc-600">タスクはありません</p>;
  }

  const renderTask = (id: string) => {
    const item = items.find((t) => t.task.id === id);
    if (!item) return null;
    const { entryId, idx, task } = item;
    if (editId === id) {
      return (
        <div className="rounded-xl bg-zinc-900 p-3">
          <input
            value={draft.summary}
            onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
            placeholder="タスク内容"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm outline-none focus:border-indigo-500"
          />
          <input
            value={draft.nextAction}
            onChange={(e) => setDraft((d) => ({ ...d, nextAction: e.target.value }))}
            placeholder="次の一歩"
            className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-emerald-300 outline-none focus:border-indigo-500"
          />
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => {
                onUpdate(entryId, idx, draft);
                setEditId(null);
              }}
              className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold active:scale-95"
            >
              保存
            </button>
            <button onClick={() => setEditId(null)} className="rounded-lg bg-zinc-700 px-3 py-1 text-xs active:scale-95">
              キャンセル
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className="flex items-start gap-2 rounded-xl bg-zinc-900 p-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium">{task.summary}</p>
          {task.nextAction && <p className="mt-1 text-sm text-emerald-400">→ {task.nextAction}</p>}
        </div>
        <div className="flex shrink-0 gap-1.5 text-xs">
          <button
            onClick={() => {
              setDraft({ ...task });
              setEditId(id);
            }}
            className="text-zinc-500 active:text-zinc-200"
            aria-label="編集"
          >
            ✏️
          </button>
          <button
            onClick={() => {
              if (confirm("このタスクを削除しますか？")) onDelete(entryId, idx);
            }}
            className="text-zinc-500 active:text-red-400"
            aria-label="削除"
          >
            🗑
          </button>
        </div>
      </div>
    );
  };

  return <ReorderList keys={items.map((t) => t.task.id)} onReorder={onReorder} renderRow={renderTask} />;
}
