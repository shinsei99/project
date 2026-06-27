"use client";

import { useEffect, useMemo, useRef, useState } from "react";

/* ---------- 型 ---------- */
type Task = { summary: string; nextAction: string };
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

type TextEntry = { id: string; ts: number; kind: "text"; input: string; result: AnalyzeResult };
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
const HISTORY_MAX = 200;
const MAX_IMAGES = 10;

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
        tasks: Array.isArray(r.tasks) ? (r.tasks as Task[]) : [],
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

export default function Home() {
  const [code, setCode] = useState("");
  const [authed, setAuthed] = useState(false);
  const [view, setView] = useState<"home" | "history">("home");

  const [text, setText] = useState("");
  const [loadingText, setLoadingText] = useState(false);

  const [previews, setPreviews] = useState<string[]>([]);
  const [loadingImage, setLoadingImage] = useState(false);
  const fileCamRef = useRef<HTMLInputElement>(null);
  const fileLibRef = useRef<HTMLInputElement>(null);

  const [history, setHistory] = useState<HistoryEntry[]>([]);
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
  }, []);

  const textEntries = useMemo(
    () => history.filter((e): e is TextEntry => e.kind === "text"),
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
    setHistory((prev) => {
      const next = prev.filter((e) => e.id !== id);
      persistHistory(next);
      return next;
    });
  }
  function clearAll() {
    if (!confirm("すべての履歴を削除しますか？（この端末から消えます。タスクも消えます）")) return;
    setHistory([]);
    persistHistory([]);
  }
  function setEntryTasks(id: string, tasks: Task[]) {
    setHistory((prev) => {
      const next = prev.map((e) =>
        e.id === id && e.kind === "text" ? { ...e, result: { ...e.result, tasks } } : e
      );
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
      addEntry({ id: newId(), ts: Date.now(), kind: "text", input: text.trim(), result: data });
      setText(""); // 反映されたら入力欄を白紙に
    } catch (err) {
      setError(err instanceof Error ? err.message : "解析に失敗しました");
    } finally {
      setLoadingText(false);
    }
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
            {view === "home" ? `🕘 履歴${history.length ? `(${history.length})` : ""}` : "← もどる"}
          </button>
          <button onClick={logout} className="text-xs text-zinc-500 active:text-zinc-300">
            ロック
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      {view === "history" ? (
        <HistoryView history={history} onDelete={deleteEntry} onClear={clearAll} onViewImage={setLightbox} />
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
            <button
              onClick={analyzeText}
              disabled={loadingText || !text.trim()}
              className="mt-3 w-full rounded-2xl bg-indigo-600 py-3.5 font-semibold disabled:opacity-40 active:scale-[0.98]"
            >
              {loadingText ? "整理中…" : "🧹 脳を空っぽにする（タスク/アイデア/ビジネス/その他に分類）"}
            </button>
          </section>

          {/* タスク（全件トップに常時表示・編集削除可） */}
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-semibold text-zinc-300">📋 タスク</h2>
            <TaskMaster items={taskItems} onUpdate={updateTask} onDelete={deleteTask} />
          </section>

          {/* メモ（タイトルのみ・タップで詳細） */}
          {textEntries.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-zinc-300">📝 メモ</h2>
              <div className="flex flex-col gap-2">
                {textEntries.map((e) => (
                  <MemoRow key={e.id} entry={e} />
                ))}
              </div>
            </section>
          )}

          {/* スクラップ */}
          <section className="border-t border-zinc-800 pt-6">
            <h2 className="mb-1 text-sm font-semibold text-zinc-300">📷 写真スクラップ</h2>
            <p className="mb-3 text-xs text-zinc-600">最大{MAX_IMAGES}枚。複数ページをまとめて1つに整理します。</p>
            <input ref={fileCamRef} type="file" accept="image/*" capture="environment" onChange={onPickImages} className="hidden" />
            <input ref={fileLibRef} type="file" accept="image/*" multiple onChange={onPickImages} className="hidden" />
            <div className="flex gap-2">
              <button onClick={() => fileCamRef.current?.click()} disabled={previews.length >= MAX_IMAGES} className="flex-1 rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/50 py-4 text-sm text-zinc-300 disabled:opacity-40 active:scale-[0.98]">
                📷 撮影
              </button>
              <button onClick={() => fileLibRef.current?.click()} disabled={previews.length >= MAX_IMAGES} className="flex-1 rounded-2xl border border-dashed border-zinc-700 bg-zinc-900/50 py-4 text-sm text-zinc-300 disabled:opacity-40 active:scale-[0.98]">
                🖼 アルバムから選ぶ
              </button>
            </div>

            {previews.length > 0 && (
              <div className="mt-4">
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

            {imageEntries.length > 0 && (
              <div className="mt-5 flex flex-col gap-2">
                {imageEntries.map((e) => (
                  <ScrapRow key={e.id} entry={e} onViewImage={setLightbox} />
                ))}
              </div>
            )}
          </section>
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
    </main>
  );
}

/* ---------- 履歴ビュー（検索つき・詳細はここ） ---------- */
function HistoryView({
  history,
  onDelete,
  onClear,
  onViewImage,
}: {
  history: HistoryEntry[];
  onDelete: (id: string) => void;
  onClear: () => void;
  onViewImage: (src: string) => void;
}) {
  const [query, setQuery] = useState("");
  if (history.length === 0) {
    return <div className="mt-16 text-center text-sm text-zinc-600">まだ履歴はありません。<br />整理すると、ここに保存されます。</div>;
  }
  const q = query.trim().toLowerCase();
  const filtered = q ? history.filter((e) => entryText(e).toLowerCase().includes(q)) : history;
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
        <p className="text-xs text-zinc-500">{q ? `${filtered.length} / ${history.length}件` : `${history.length}件`}</p>
        <button onClick={onClear} className="text-xs text-red-400 active:text-red-300">すべて消去</button>
      </div>
      {filtered.length === 0 ? (
        <p className="mt-8 text-center text-sm text-zinc-600">「{query}」に一致する履歴はありません</p>
      ) : (
        filtered.map((e) =>
          e.kind === "text" ? (
            <MemoRow key={e.id} entry={e} onDelete={onDelete} />
          ) : (
            <ScrapRow key={e.id} entry={e} onViewImage={onViewImage} onDelete={onDelete} />
          )
        )
      )}
    </div>
  );
}

/* ---------- メモ行（タイトル＋タップで詳細） ---------- */
function MemoRow({ entry, onDelete }: { entry: TextEntry; onDelete?: (id: string) => void }) {
  const r = entry.result;
  const title = r.title || entry.input.slice(0, 24) || "無題";
  return (
    <details className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950/40">
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 p-3">
        <span className="min-w-0 flex-1 truncate text-sm">📝 {title}</span>
        <span className="shrink-0 text-xs text-zinc-600">{formatDate(entry.ts)}</span>
      </summary>
      <div className="px-3 pb-3">
        <MemoDetail result={r} />
        {onDelete && (
          <button onClick={() => onDelete(entry.id)} className="mt-3 text-xs text-zinc-600 active:text-red-400">
            🗑 この項目を削除
          </button>
        )}
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

/* ---------- スクラップ行（タイトル＋タップで詳細・元写真） ---------- */
function ScrapRow({
  entry,
  onViewImage,
  onDelete,
}: {
  entry: ImageEntry;
  onViewImage: (src: string) => void;
  onDelete?: (id: string) => void;
}) {
  const r = entry.result;
  return (
    <details className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950/40">
      <summary className="flex cursor-pointer select-none items-center justify-between gap-2 p-3">
        <span className="min-w-0 flex-1 truncate text-sm">
          📷 {r.title || "スクラップ"}
          {entry.count && entry.count > 1 ? `（${entry.count}枚）` : ""}
        </span>
        <span className="shrink-0 text-xs text-zinc-600">{formatDate(entry.ts)}</span>
      </summary>
      <div className="px-3 pb-3">
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
        {onDelete && (
          <button onClick={() => onDelete(entry.id)} className="mt-3 text-xs text-zinc-600 active:text-red-400">
            🗑 この項目を削除
          </button>
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
}: {
  items: { entryId: string; idx: number; task: Task; ts: number }[];
  onUpdate: (entryId: string, idx: number, t: Task) => void;
  onDelete: (entryId: string, idx: number) => void;
}) {
  const [editKey, setEditKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<Task>({ summary: "", nextAction: "" });

  if (items.length === 0) {
    return <p className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4 text-xs text-zinc-600">タスクはありません</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map(({ entryId, idx, task }) => {
        const key = `${entryId}:${idx}`;
        if (editKey === key) {
          return (
            <li key={key} className="rounded-xl bg-zinc-900 p-3">
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
                    setEditKey(null);
                  }}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold active:scale-95"
                >
                  保存
                </button>
                <button onClick={() => setEditKey(null)} className="rounded-lg bg-zinc-700 px-3 py-1 text-xs active:scale-95">
                  キャンセル
                </button>
              </div>
            </li>
          );
        }
        return (
          <li key={key} className="flex items-start gap-2 rounded-xl bg-zinc-900 p-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{task.summary}</p>
              {task.nextAction && <p className="mt-1 text-sm text-emerald-400">→ {task.nextAction}</p>}
            </div>
            <div className="flex shrink-0 gap-1.5 text-xs">
              <button
                onClick={() => {
                  setDraft({ ...task });
                  setEditKey(key);
                }}
                className="text-zinc-500 active:text-zinc-200"
                aria-label="編集"
              >
                ✏️
              </button>
              <button onClick={() => onDelete(entryId, idx)} className="text-zinc-500 active:text-red-400" aria-label="削除">
                🗑
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
