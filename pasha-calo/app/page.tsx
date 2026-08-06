"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  ACTIVITY_LEVELS,
  GOALS,
  bmiCategory,
  calcBmi,
  calcBmr,
  calcPfcTargets,
  calcTargetKcal,
  calcTdee,
  standardWeight,
  type Goal,
  type Profile,
  type Sex,
} from "@/lib/nutrition";

/* ---------- 型 ---------- */
type Slot = "朝" | "昼" | "夜" | "間食";
const SLOTS: Slot[] = ["朝", "昼", "夜", "間食"];

type Item = { name: string; calories: number };

type Meal = {
  id: string;
  ts: number;
  slot: Slot;
  food_name: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  comment: string;
  items?: Item[];
};
/* 撮影した写真は解析に送るだけで、記録には保存しない（端末の容量とプライバシーのため） */

type Analysis = {
  is_food: boolean;
  food_name: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  items: Item[];
  portion_note: string;
  confidence: "high" | "medium" | "low";
  comment: string;
};

/** 体重の記録。1日1件に丸めず、記録したぶんだけ持つ（同日複数回でもOK）。 */
type WeightEntry = { id: string; ts: number; kg: number };

const ACCESS_KEY = "pc_access_code";
const PROFILE_KEY = "pc_profile";
const MEALS_KEY = "pc_meals";
const WEIGHTS_KEY = "pc_weights";
const MEALS_MAX = 1000;
/** 1回の解析に送れる枚数。無音カメラで数枚まとめて撮れるようにしている。 */
const MAX_IMAGES = 6;

/* ---------- 小さなユーティリティ ---------- */
function newId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}
/** ローカル時刻での YYYY-MM-DD。日付集計のキーに使う。 */
function dayKey(ts: number): string {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function formatDay(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const w = ["日", "月", "火", "水", "木", "金", "土"][date.getDay()];
  const today = dayKey(Date.now());
  if (key === today) return "今日";
  const yest = dayKey(Date.now() - 86400000);
  if (key === yest) return "昨日";
  return `${m}/${d}(${w})`;
}
function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}
/**
 * 「現在日付」を外部ソースとして購読するための関数。
 * 描画中に Date.now() を読むと日付をまたいでも画面が古いままになるため、1分ごとに再評価させる。
 */
function subscribeToClock(onChange: () => void): () => void {
  const id = setInterval(onChange, 60000);
  return () => clearInterval(id);
}

/** 時刻から食事区分を推測する（記録時の初期値）。 */
function guessSlot(ts: number): Slot {
  const h = new Date(ts).getHours();
  if (h < 10) return "朝";
  if (h < 15) return "昼";
  if (h < 21) return "夜";
  return "間食";
}

/* ---------- 保存（localStorage。容量超過時はサムネ→古い記録の順に間引く） ---------- */
function loadMeals(): Meal[] {
  try {
    const raw = localStorage.getItem(MEALS_KEY);
    return raw ? (JSON.parse(raw) as Meal[]) : [];
  } catch {
    return [];
  }
}
function persistMeals(list: Meal[]) {
  const base = list.slice(0, MEALS_MAX);
  try {
    localStorage.setItem(MEALS_KEY, JSON.stringify(base));
  } catch {
    // 写真を保存していないので通常あふれないが、念のため古い記録を捨てて再試行する
    try {
      localStorage.setItem(MEALS_KEY, JSON.stringify(base.slice(0, 300)));
    } catch {
      /* それでも保存できない場合はあきらめる（画面上のデータは保持される） */
    }
  }
}
function loadProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Profile;
    // 目標体重を後から追加したため、古い保存データには存在しない。標準体重で補う。
    if (typeof p.targetWeight !== "number" || !(p.targetWeight > 0)) {
      p.targetWeight = standardWeight(p.height);
    }
    return p;
  } catch {
    return null;
  }
}

function loadWeights(): WeightEntry[] {
  try {
    const raw = localStorage.getItem(WEIGHTS_KEY);
    return raw ? (JSON.parse(raw) as WeightEntry[]) : [];
  } catch {
    return [];
  }
}
function persistWeights(list: WeightEntry[]) {
  try {
    localStorage.setItem(WEIGHTS_KEY, JSON.stringify(list));
  } catch {
    /* 体重データは軽いので通常あふれない */
  }
}

/* ---------- 画像処理（送信用は縮小、保存用はサムネ） ---------- */
async function fileToDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = () => reject(new Error("読み込みに失敗しました"));
    r.readAsDataURL(file);
  });
}
async function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("画像を開けませんでした"));
    img.src = src;
  });
}
/** 送信サイズの上限。料理の判別には十分で、6枚送ってもリクエストが重くならない値。 */
const SEND_MAX_PX = 1280;
const SEND_QUALITY = 0.8;

/** <img> や <video> を指定サイズ以内に縮小して JPEG の dataURL にする。 */
function drawResized(
  src: HTMLImageElement | HTMLVideoElement,
  srcW: number,
  srcH: number,
  maxSize: number,
  quality: number
): string {
  const scale = Math.min(1, maxSize / Math.max(srcW, srcH));
  const w = Math.max(1, Math.round(srcW * scale));
  const h = Math.max(1, Math.round(srcH * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d")!.drawImage(src, 0, 0, w, h);
  return canvas.toDataURL("image/jpeg", quality);
}

/** ライブラリで選んだファイルを送信用に縮小する。 */
async function prepareImage(file: File): Promise<string> {
  const img = await loadImage(await fileToDataURL(file));
  return drawResized(img, img.width, img.height, SEND_MAX_PX, SEND_QUALITY);
}

/* ================= 画面 ================= */
export default function Page() {
  /* 認証 */
  const [authed, setAuthed] = useState(false);
  const [code, setCode] = useState("");
  const [ready, setReady] = useState(false);

  /* データ（localStorageから初回描画時に復元。サーバー描画時は空で、画面は下の ready 待ちに入る） */
  const [profile, setProfile] = useState<Profile | null>(() =>
    typeof window === "undefined" ? null : loadProfile()
  );
  const [meals, setMeals] = useState<Meal[]>(() =>
    typeof window === "undefined" ? [] : loadMeals()
  );
  const [weights, setWeights] = useState<WeightEntry[]>(() =>
    typeof window === "undefined" ? [] : loadWeights()
  );

  /* 画面 */
  const [view, setView] = useState<"home" | "weight" | "log" | "settings">("home");
  const [error, setError] = useState("");

  /* 保存済みコードの検証。ログイン画面が一瞬ちらつかないよう、判定が終わるまで ready にしない */
  useEffect(() => {
    const saved = localStorage.getItem(ACCESS_KEY);
    const check = saved
      ? fetch("/api/auth", { headers: { "x-access-code": saved } })
          .then((res) => {
            if (res.ok) {
              setCode(saved);
              setAuthed(true);
            } else {
              localStorage.removeItem(ACCESS_KEY);
            }
          })
          .catch(() => {
            /* オフライン時は入力画面に戻すだけ */
          })
      : Promise.resolve();
    check.finally(() => setReady(true));
  }, []);

  function saveProfile(p: Profile) {
    setProfile(p);
    localStorage.setItem(PROFILE_KEY, JSON.stringify(p));
  }
  function addMeal(meal: Meal) {
    setMeals((prev) => {
      const next = [meal, ...prev];
      persistMeals(next);
      return next;
    });
  }
  function deleteMeal(id: string) {
    setMeals((prev) => {
      const next = prev.filter((m) => m.id !== id);
      persistMeals(next);
      return next;
    });
  }

  /**
   * 体重を記録し、プロフィールの体重も最新値に更新する。
   * 目標カロリーが自動計算なら、痩せた分だけ必要カロリーも下がるので再計算する。
   */
  function addWeight(kg: number) {
    const entry: WeightEntry = { id: newId(), ts: Date.now(), kg };
    setWeights((prev) => {
      const next = [entry, ...prev].sort((a, b) => b.ts - a.ts);
      persistWeights(next);
      return next;
    });
    if (profile) {
      const updated: Profile = { ...profile, weight: kg };
      if (updated.autoTarget) updated.targetKcal = calcTargetKcal(updated);
      saveProfile(updated);
    }
  }
  function deleteWeight(id: string) {
    setWeights((prev) => {
      const next = prev.filter((w) => w.id !== id);
      persistWeights(next);
      return next;
    });
  }

  if (!ready) {
    return <main className="flex min-h-dvh items-center justify-center text-zinc-600">読み込み中…</main>;
  }

  if (!authed) {
    return (
      <LoginView
        onSuccess={(c) => {
          localStorage.setItem(ACCESS_KEY, c);
          setCode(c);
          setAuthed(true);
        }}
      />
    );
  }

  if (!profile) {
    return <Onboarding onDone={saveProfile} />;
  }

  return (
    <main className="mx-auto max-w-md px-4 pb-24 pt-5">
      <header className="mb-5 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">
          パシャカロ<span className="text-orange-400">！</span>
        </h1>
        <button
          onClick={() => setView(view === "settings" ? "home" : "settings")}
          className="text-xs text-zinc-500 active:text-zinc-300"
        >
          {view === "settings" ? "閉じる" : "設定"}
        </button>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {view === "settings" ? (
        <SettingsView
          profile={profile}
          onSave={(p) => {
            saveProfile(p);
            setView("home");
          }}
          onLogout={() => {
            localStorage.removeItem(ACCESS_KEY);
            setAuthed(false);
            setCode("");
          }}
        />
      ) : view === "weight" ? (
        <WeightView
          profile={profile}
          weights={weights}
          onAdd={addWeight}
          onDelete={deleteWeight}
          onSetTarget={(kg) => saveProfile({ ...profile, targetWeight: kg })}
        />
      ) : view === "log" ? (
        <LogView meals={meals} onDelete={deleteMeal} />
      ) : (
        <HomeView
          profile={profile}
          meals={meals}
          code={code}
          onAdd={addMeal}
          onDelete={deleteMeal}
          onError={setError}
        />
      )}

      {view !== "settings" && (
        <nav
          className="fixed inset-x-0 bottom-0 border-t border-zinc-900 bg-black/90 backdrop-blur"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          <div className="mx-auto flex max-w-md">
            {(
              [
                ["home", "🏠 ホーム"],
                ["weight", "⚖️ 体重"],
                ["log", "📖 履歴"],
              ] as const
            ).map(([v, label]) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`flex-1 py-3 text-sm ${
                  view === v ? "text-orange-400" : "text-zinc-500"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </nav>
      )}
    </main>
  );
}

/* ---------- ログイン ---------- */
function LoginView({ onSuccess }: { onSuccess: (code: string) => void }) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const c = value.trim();
    if (!c) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/auth", { headers: { "x-access-code": c } });
      if (!res.ok) {
        setError("アクセスコードが違います");
        return;
      }
      onSuccess(c);
    } catch {
      setError("通信に失敗しました。電波の良い場所で再度お試しください。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6">
      <div className="mb-8 text-center">
        <div className="mb-2 text-5xl">🍽</div>
        <h1 className="text-2xl font-bold">
          パシャカロ<span className="text-orange-400">！</span>
        </h1>
        <p className="mt-1 text-sm text-zinc-500">撮るだけカロリー記録</p>
      </div>
      <form onSubmit={submit} className="w-full max-w-xs space-y-3">
        <div className="relative">
          <input
            type={show ? "text" : "password"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            placeholder="アクセスコード"
            className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 pr-12 text-center text-lg tracking-widest outline-none focus:border-orange-500"
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-lg"
            aria-label={show ? "コードを隠す" : "コードを表示"}
          >
            {show ? "🙈" : "👁"}
          </button>
        </div>
        {error && <p className="text-center text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="w-full rounded-xl bg-orange-600 py-3 font-semibold disabled:opacity-40 active:scale-[0.98]"
        >
          {busy ? "確認中…" : "はじめる"}
        </button>
        <p className="text-center text-xs text-zinc-600">一度入れれば次回から自動でログインします</p>
      </form>
    </main>
  );
}

/* ---------- 初期設定 ---------- */
const emptyForm = {
  sex: "male" as Sex,
  age: "",
  height: "",
  weight: "",
  targetWeight: "",
  activity: 1.375,
  goal: "lose" as Goal,
};

function Onboarding({ onDone }: { onDone: (p: Profile) => void }) {
  const [form, setForm] = useState(emptyForm);
  const age = Number(form.age);
  const height = Number(form.height);
  const weight = Number(form.weight);
  const valid = age >= 10 && age <= 100 && height >= 100 && height <= 250 && weight >= 25 && weight <= 250;

  const preview = valid
    ? calcTargetKcal({ sex: form.sex, age, height, weight, activity: form.activity, goal: form.goal })
    : 0;

  return (
    <main className="mx-auto max-w-md px-5 pb-10 pt-8">
      <h1 className="text-2xl font-bold">
        パシャカロ<span className="text-orange-400">！</span>
      </h1>
      <p className="mt-1 mb-6 text-sm text-zinc-500">
        まずはあなたの1日の目標カロリーを計算します
      </p>

      <ProfileForm form={form} setForm={setForm} />

      {valid && (
        <div className="mt-6 rounded-2xl border border-orange-900/60 bg-orange-950/30 p-4 text-center">
          <p className="text-xs text-zinc-400">1日の目標摂取カロリー</p>
          <p className="mt-1 text-3xl font-bold text-orange-400">
            {preview.toLocaleString()}
            <span className="ml-1 text-base font-normal text-zinc-400">kcal</span>
          </p>
          <p className="mt-2 text-[11px] text-zinc-500">
            基礎代謝 {calcBmr({ sex: form.sex, age, height, weight }).toLocaleString()} / 消費量{" "}
            {calcTdee({ sex: form.sex, age, height, weight, activity: form.activity }).toLocaleString()} kcal
          </p>
        </div>
      )}

      <button
        disabled={!valid}
        onClick={() =>
          onDone({
            sex: form.sex,
            age,
            height,
            weight,
            activity: form.activity,
            goal: form.goal,
            targetWeight: Number(form.targetWeight) > 0
              ? Math.round(Number(form.targetWeight) * 10) / 10
              : standardWeight(height),
            targetKcal: preview,
            autoTarget: true,
          })
        }
        className="mt-6 w-full rounded-xl bg-orange-600 py-3.5 font-semibold disabled:opacity-40 active:scale-[0.98]"
      >
        はじめる
      </button>
      <p className="mt-3 text-center text-xs text-zinc-600">
        ハリス・ベネディクト方程式で算出。あとから設定で変更できます
      </p>
    </main>
  );
}

type FormState = typeof emptyForm;

function ProfileForm({
  form,
  setForm,
}: {
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
}) {
  const field =
    "w-full rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-lg outline-none focus:border-orange-500";
  const heightNum = Number(form.height);
  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-xs text-zinc-500">性別</label>
        <div className="grid grid-cols-2 gap-2">
          {(["male", "female"] as Sex[]).map((s) => (
            <button
              key={s}
              onClick={() => setForm((f) => ({ ...f, sex: s }))}
              className={`rounded-xl border py-3 ${
                form.sex === s
                  ? "border-orange-500 bg-orange-950/40 text-orange-300"
                  : "border-zinc-800 bg-zinc-900 text-zinc-400"
              }`}
            >
              {s === "male" ? "男性" : "女性"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {(
          [
            ["age", "年齢", "歳"],
            ["height", "身長", "cm"],
            ["weight", "体重", "kg"],
          ] as const
        ).map(([key, label, unit]) => (
          <div key={key}>
            <label className="mb-1.5 block text-xs text-zinc-500">
              {label}（{unit}）
            </label>
            <input
              type="number"
              inputMode="decimal"
              value={form[key]}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              className={field}
            />
          </div>
        ))}
      </div>

      <div>
        <label className="mb-1.5 block text-xs text-zinc-500">運動量</label>
        <div className="space-y-2">
          {ACTIVITY_LEVELS.map((a) => (
            <button
              key={a.value}
              onClick={() => setForm((f) => ({ ...f, activity: a.value }))}
              className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left ${
                form.activity === a.value
                  ? "border-orange-500 bg-orange-950/40"
                  : "border-zinc-800 bg-zinc-900"
              }`}
            >
              <span className="text-sm">{a.label}</span>
              <span className="text-xs text-zinc-500">{a.hint}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-xs text-zinc-500">目標</label>
        <div className="grid grid-cols-3 gap-2">
          {GOALS.map((g) => (
            <button
              key={g.value}
              onClick={() => setForm((f) => ({ ...f, goal: g.value }))}
              className={`rounded-xl border py-3 text-sm ${
                form.goal === g.value
                  ? "border-orange-500 bg-orange-950/40 text-orange-300"
                  : "border-zinc-800 bg-zinc-900 text-zinc-400"
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-xs text-zinc-500">目標体重（kg）</label>
        <input
          type="number"
          inputMode="decimal"
          step="0.1"
          value={form.targetWeight}
          onChange={(e) => setForm((f) => ({ ...f, targetWeight: e.target.value }))}
          placeholder={heightNum >= 100 ? `標準体重 ${standardWeight(heightNum).toFixed(1)}` : ""}
          className={field}
        />
        <p className="mt-1 text-[11px] text-zinc-600">
          未入力なら標準体重（BMI22）が目標になります
        </p>
      </div>
    </div>
  );
}

/* ---------- ホーム ---------- */
function HomeView({
  profile,
  meals,
  code,
  onAdd,
  onDelete,
  onError,
}: {
  profile: Profile;
  meals: Meal[];
  code: string;
  onAdd: (m: Meal) => void;
  onDelete: (id: string) => void;
  onError: (msg: string) => void;
}) {
  const libRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const camStreamRef = useRef<MediaStream | null>(null);

  /** 解析に送る写真（dataURL）。記録には残さず、保存が終わったら破棄する。 */
  const [shots, setShots] = useState<string[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<Analysis | null>(null);
  const [defaultSlot, setDefaultSlot] = useState<Slot>("昼");

  /* 無音カメラ（アプリ内カメラ。iOSの標準カメラと違いシャッター音が鳴らない） */
  const [camOpen, setCamOpen] = useState(false);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [flash, setFlash] = useState(false);

  // 現在日付は時計という外部ソース。描画中に直接読まず、日付をまたいだら自動更新されるようにする。
  const today = useSyncExternalStore(
    subscribeToClock,
    () => dayKey(Date.now()),
    () => ""
  );
  const todayMeals = useMemo(() => meals.filter((m) => dayKey(m.ts) === today), [meals, today]);
  const total = useMemo(
    () =>
      todayMeals.reduce(
        (acc, m) => ({
          calories: acc.calories + m.calories,
          protein: acc.protein + m.protein,
          fat: acc.fat + m.fat,
          carbs: acc.carbs + m.carbs,
        }),
        { calories: 0, protein: 0, fat: 0, carbs: 0 }
      ),
    [todayMeals]
  );

  const pfcTarget = calcPfcTargets(profile.targetKcal, profile.weight);
  const remaining = profile.targetKcal - total.calories;
  const pct = Math.min(100, Math.round((total.calories / Math.max(1, profile.targetKcal)) * 100));
  const over = total.calories > profile.targetKcal;

  /* カメラを開いている間だけ映像を流す（前後カメラ切替時は入れ直す） */
  useEffect(() => {
    if (!camOpen) return;
    let cancelled = false;
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
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
        onError(
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
  }, [camOpen, facing, onError]);

  function openCamera() {
    if (shots.length >= MAX_IMAGES) {
      onError(`写真は最大${MAX_IMAGES}枚までです`);
      return;
    }
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      onError("このブラウザはカメラに対応していません。「ライブラリから選ぶ」をお使いください。");
      return;
    }
    onError("");
    setCamOpen(true); // 実際のストリーム開始は useEffect で
  }

  /** 映像から1枚切り出す。標準カメラを使わないのでシャッター音が鳴らない。 */
  function captureSilent() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    if (shots.length >= MAX_IMAGES) {
      onError(`写真は最大${MAX_IMAGES}枚までです`);
      return;
    }
    const url = drawResized(video, video.videoWidth, video.videoHeight, SEND_MAX_PX, SEND_QUALITY);
    setShots((prev) => [...prev, url].slice(0, MAX_IMAGES));
    // 音の代わりに一瞬フラッシュして撮れたことを知らせる
    setFlash(true);
    setTimeout(() => setFlash(false), 130);
  }

  async function onPickLibrary(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;
    const room = MAX_IMAGES - shots.length;
    if (room <= 0) {
      onError(`写真は最大${MAX_IMAGES}枚までです`);
      return;
    }
    onError("");
    try {
      const prepared = await Promise.all(files.slice(0, room).map(prepareImage));
      setShots((prev) => [...prev, ...prepared].slice(0, MAX_IMAGES));
    } catch {
      onError("画像を読み込めませんでした");
    }
  }

  async function analyze() {
    if (shots.length === 0) return;
    onError("");
    setResult(null);
    setAnalyzing(true);
    try {
      const res = await fetch("/api/analyze-meal", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-access-code": code },
        body: JSON.stringify({ images: shots }),
      });
      const data = await res.json();
      if (!res.ok) {
        onError(data?.error ?? "解析に失敗しました");
        return;
      }
      if (!data.is_food) {
        onError(data.comment || "食事の写真を撮ってください");
        return;
      }
      setDefaultSlot(guessSlot(Date.now()));
      setResult(data as Analysis);
    } catch {
      onError("解析に失敗しました。通信環境を確認してください。");
    } finally {
      setAnalyzing(false);
    }
  }

  /** 写真はここで破棄する（記録には保存しない） */
  function reset() {
    setResult(null);
    setShots([]);
  }

  return (
    <>
      {/* 今日のサマリー */}
      <section className="rounded-2xl border border-zinc-900 bg-zinc-950 p-5">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs text-zinc-500">今日の摂取</p>
            <p className="mt-0.5 text-3xl font-bold tabular-nums">
              {total.calories.toLocaleString()}
              <span className="ml-1 text-sm font-normal text-zinc-500">
                / {profile.targetKcal.toLocaleString()} kcal
              </span>
            </p>
          </div>
          <div className="text-right">
            <p className={`text-sm tabular-nums ${over ? "text-red-400" : "text-emerald-400"}`}>
              {over ? `+${(-remaining).toLocaleString()}` : `のこり ${remaining.toLocaleString()}`}
            </p>
            <p className="mt-0.5 text-[11px] tabular-nums text-zinc-600">
              {profile.weight.toFixed(1)}kg / BMI {calcBmi(profile.weight, profile.height).toFixed(1)}
            </p>
          </div>
        </div>

        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-zinc-800">
          <div
            className={`h-full rounded-full transition-all ${over ? "bg-red-500" : "bg-orange-500"}`}
            style={{ width: `${pct}%` }}
          />
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3">
          {(
            [
              ["P たんぱく", total.protein, pfcTarget.protein, "bg-sky-500"],
              ["F 脂質", total.fat, pfcTarget.fat, "bg-amber-500"],
              ["C 炭水化", total.carbs, pfcTarget.carbs, "bg-violet-500"],
            ] as const
          ).map(([label, value, target, color]) => (
            <div key={label}>
              <div className="flex items-baseline justify-between">
                <span className="text-[11px] text-zinc-500">{label}</span>
                <span className="text-[11px] tabular-nums text-zinc-400">
                  {value}/{target}g
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={`h-full rounded-full ${color}`}
                  style={{ width: `${Math.min(100, (value / Math.max(1, target)) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 撮影・選択 */}
      <input ref={libRef} type="file" accept="image/*" multiple onChange={onPickLibrary} className="hidden" />

      {!result && (
        <section className="mt-5">
          {shots.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {shots.map((s, i) => (
                <div key={i} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={s}
                    alt=""
                    className={`h-20 w-20 rounded-xl object-cover ${analyzing ? "animate-pulse" : ""}`}
                  />
                  {!analyzing && (
                    <button
                      onClick={() => setShots((prev) => prev.filter((_, j) => j !== i))}
                      className="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full border border-zinc-700 bg-zinc-900 text-xs"
                      aria-label="この写真を外す"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {shots.length === 0 ? (
            <>
              <button
                onClick={openCamera}
                className="w-full rounded-2xl bg-orange-600 py-5 text-lg font-bold active:scale-[0.98]"
              >
                📸 写真を撮る（無音）
              </button>
              <button
                onClick={() => libRef.current?.click()}
                className="mt-2 w-full rounded-xl border border-zinc-800 py-3 text-sm text-zinc-400 active:scale-[0.98]"
              >
                🖼 ライブラリから選ぶ
              </button>
            </>
          ) : (
            <>
              <button
                onClick={analyze}
                disabled={analyzing}
                className="w-full rounded-2xl bg-orange-600 py-5 text-lg font-bold disabled:opacity-50 active:scale-[0.98]"
              >
                {analyzing ? "AIが解析中…" : `この${shots.length}枚でカロリーを計算`}
              </button>
              <div className="mt-2 grid grid-cols-3 gap-2">
                <button
                  onClick={openCamera}
                  disabled={analyzing || shots.length >= MAX_IMAGES}
                  className="rounded-xl border border-zinc-800 py-2.5 text-xs text-zinc-400 disabled:opacity-40 active:scale-[0.98]"
                >
                  📸 追加で撮る
                </button>
                <button
                  onClick={() => libRef.current?.click()}
                  disabled={analyzing || shots.length >= MAX_IMAGES}
                  className="rounded-xl border border-zinc-800 py-2.5 text-xs text-zinc-400 disabled:opacity-40 active:scale-[0.98]"
                >
                  🖼 追加で選ぶ
                </button>
                <button
                  onClick={() => setShots([])}
                  disabled={analyzing}
                  className="rounded-xl border border-zinc-800 py-2.5 text-xs text-zinc-500 disabled:opacity-40 active:scale-[0.98]"
                >
                  すべて外す
                </button>
              </div>
            </>
          )}
          <p className="mt-2 text-center text-[11px] leading-relaxed text-zinc-600">
            最大{MAX_IMAGES}枚。同じ食事を別角度で撮ると精度が上がります
            <br />
            写真は解析に使うだけで、端末にもサーバーにも保存されません
          </p>
        </section>
      )}

      {result && (
        <ResultCard
          analysis={result}
          previews={shots}
          defaultSlot={defaultSlot}
          onCancel={reset}
          onSave={(meal) => {
            onAdd(meal);
            reset();
          }}
        />
      )}

      {/* 今日の記録 */}
      <section className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-zinc-400">今日の記録</h2>
        {todayMeals.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-800 px-4 py-6 text-center text-sm text-zinc-600">
            まだ記録がありません
          </p>
        ) : (
          <ul className="space-y-2">
            {todayMeals.map((m) => (
              <MealRow key={m.id} meal={m} onDelete={onDelete} />
            ))}
          </ul>
        )}
      </section>

      {/* 無音カメラ（アプリ内カメラ・シャッター音なし） */}
      {camOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="min-h-0 w-full flex-1 object-contain"
          />

          {/* 撮影時の白フラッシュ（音の代わり） */}
          {flash && <div className="pointer-events-none absolute inset-0 bg-white" />}

          <button
            onClick={() => setCamOpen(false)}
            className="absolute left-4 top-5 flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-lg text-white active:bg-black/70"
            aria-label="閉じる"
          >
            ✕
          </button>
          <span className="absolute left-1/2 top-6 -translate-x-1/2 text-sm text-white/90">
            {shots.length} / {MAX_IMAGES}枚
          </span>
          <button
            onClick={() => setFacing((f) => (f === "environment" ? "user" : "environment"))}
            className="absolute right-4 top-5 flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-lg active:bg-black/70"
            aria-label="カメラ切替"
          >
            🔄
          </button>

          {/* 直前に撮った写真（撮れているか確認用） */}
          {shots.length > 0 && (
            <div className="absolute bottom-28 left-4 flex gap-1.5">
              {shots.slice(-3).map((s, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  src={s}
                  alt=""
                  className="h-12 w-12 rounded-lg border border-white/30 object-cover"
                />
              ))}
            </div>
          )}

          <div className="relative flex items-center justify-center bg-black py-6">
            <button
              onClick={captureSilent}
              disabled={shots.length >= MAX_IMAGES}
              aria-label="撮影（無音）"
              className="h-[68px] w-[68px] rounded-full border-[5px] border-white bg-white/25 active:bg-white/50 disabled:opacity-40"
            />
            <button
              onClick={() => setCamOpen(false)}
              className="absolute right-6 rounded-xl bg-white/15 px-4 py-2 text-sm text-white active:bg-white/30"
            >
              完了{shots.length ? `（${shots.length}）` : ""}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/* ---------- 解析結果の確認カード ---------- */
function ResultCard({
  analysis,
  previews,
  defaultSlot,
  onCancel,
  onSave,
}: {
  analysis: Analysis;
  /** 確認用に表示するだけの写真。記録には保存しない。 */
  previews: string[];
  defaultSlot: Slot;
  onCancel: () => void;
  onSave: (m: Meal) => void;
}) {
  const [name, setName] = useState(analysis.food_name);
  const [slot, setSlot] = useState<Slot>(defaultSlot);
  const [mult, setMult] = useState(1);
  const [values, setValues] = useState({
    calories: analysis.calories,
    protein: analysis.protein,
    fat: analysis.fat,
    carbs: analysis.carbs,
  });

  /** 分量倍率。AIの推定値を基準にまとめてスケールする（AIが苦手な「量」を人が直すため）。 */
  function applyMult(m: number) {
    setMult(m);
    setValues({
      calories: Math.round(analysis.calories * m),
      protein: Math.round(analysis.protein * m),
      fat: Math.round(analysis.fat * m),
      carbs: Math.round(analysis.carbs * m),
    });
  }

  const confidenceLabel = { high: "推定の確度: 高", medium: "推定の確度: 中", low: "推定の確度: 低" }[
    analysis.confidence
  ];

  return (
    <section className="mt-5 rounded-2xl border border-orange-900/60 bg-zinc-950 p-4">
      {previews.length > 0 && (
        <div className="mb-3 flex gap-2">
          {previews.map((p, i) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={i} src={p} alt="" className="h-16 w-16 rounded-lg object-cover" />
          ))}
        </div>
      )}

      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 font-semibold outline-none focus:border-orange-500"
      />

      {analysis.items.length > 1 && (
        <ul className="mt-2 space-y-0.5 text-xs text-zinc-500">
          {analysis.items.map((it, i) => (
            <li key={i} className="flex justify-between">
              <span>・{it.name}</span>
              <span className="tabular-nums">{it.calories} kcal</span>
            </li>
          ))}
        </ul>
      )}

      {/* 分量の補正 */}
      <div className="mt-3">
        <p className="mb-1.5 text-[11px] text-zinc-500">
          分量の補正{analysis.portion_note ? `（AI: ${analysis.portion_note}）` : ""}
        </p>
        <div className="grid grid-cols-5 gap-1.5">
          {[0.5, 0.75, 1, 1.5, 2].map((m) => (
            <button
              key={m}
              onClick={() => applyMult(m)}
              className={`rounded-lg border py-2 text-sm ${
                mult === m
                  ? "border-orange-500 bg-orange-950/40 text-orange-300"
                  : "border-zinc-800 bg-zinc-900 text-zinc-400"
              }`}
            >
              ×{m}
            </button>
          ))}
        </div>
      </div>

      {/* 数値（手入力で微調整可） */}
      <div className="mt-3 grid grid-cols-4 gap-2">
        {(
          [
            ["calories", "kcal"],
            ["protein", "P g"],
            ["fat", "F g"],
            ["carbs", "C g"],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <label className="mb-1 block text-[11px] text-zinc-500">{label}</label>
            <input
              type="number"
              inputMode="numeric"
              value={values[key]}
              onChange={(e) =>
                setValues((v) => ({ ...v, [key]: Math.max(0, Math.round(Number(e.target.value) || 0)) }))
              }
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-2 text-center tabular-nums outline-none focus:border-orange-500"
            />
          </div>
        ))}
      </div>

      {/* 食事区分 */}
      <div className="mt-3 grid grid-cols-4 gap-1.5">
        {SLOTS.map((s) => (
          <button
            key={s}
            onClick={() => setSlot(s)}
            className={`rounded-lg border py-2 text-sm ${
              slot === s
                ? "border-orange-500 bg-orange-950/40 text-orange-300"
                : "border-zinc-800 bg-zinc-900 text-zinc-400"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {analysis.comment && (
        <p className="mt-3 rounded-lg bg-zinc-900 px-3 py-2 text-xs leading-relaxed text-zinc-400">
          💬 {analysis.comment}
        </p>
      )}
      <p className="mt-2 text-center text-[11px] text-zinc-600">
        {confidenceLabel}・数値はあくまで目安です
      </p>

      <div className="mt-4 flex gap-2">
        <button
          onClick={onCancel}
          className="flex-1 rounded-xl border border-zinc-800 py-3 text-sm text-zinc-400 active:scale-[0.98]"
        >
          やり直す
        </button>
        <button
          onClick={() =>
            onSave({
              id: newId(),
              ts: Date.now(),
              slot,
              food_name: name.trim() || "料理",
              ...values,
              comment: analysis.comment,
              items: analysis.items,
            })
          }
          className="flex-[2] rounded-xl bg-orange-600 py-3 font-semibold active:scale-[0.98]"
        >
          記録する
        </button>
      </div>
    </section>
  );
}

/* ---------- 記録の1行 ---------- */
function MealRow({ meal, onDelete }: { meal: Meal; onDelete: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-xl border border-zinc-900 bg-zinc-950">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 p-3 text-left">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-lg">
          {{ 朝: "🌅", 昼: "☀️", 夜: "🌙", 間食: "🍩" }[meal.slot]}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{meal.food_name}</p>
          <p className="text-[11px] text-zinc-500">
            {meal.slot}・{formatTime(meal.ts)}・P{meal.protein} F{meal.fat} C{meal.carbs}
          </p>
        </div>
        <p className="shrink-0 tabular-nums text-sm font-semibold text-orange-400">
          {meal.calories.toLocaleString()}
          <span className="ml-0.5 text-[10px] font-normal text-zinc-500">kcal</span>
        </p>
      </button>
      {open && (
        <div className="border-t border-zinc-900 px-3 py-2">
          {meal.comment && <p className="mb-2 text-xs text-zinc-500">💬 {meal.comment}</p>}
          <button
            onClick={() => {
              if (confirm(`「${meal.food_name}」を削除しますか？`)) onDelete(meal.id);
            }}
            className="text-xs text-red-400 active:text-red-300"
          >
            削除する
          </button>
        </div>
      )}
    </li>
  );
}

/* ---------- 履歴 ---------- */
function LogView({ meals, onDelete }: { meals: Meal[]; onDelete: (id: string) => void }) {
  const groups = useMemo(() => {
    const map = new Map<string, Meal[]>();
    for (const m of meals) {
      const key = dayKey(m.ts);
      const list = map.get(key);
      if (list) list.push(m);
      else map.set(key, [m]);
    }
    return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [meals]);

  if (groups.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-zinc-800 px-4 py-10 text-center text-sm text-zinc-600">
        まだ記録がありません
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map(([key, list]) => {
        const sum = list.reduce((a, m) => a + m.calories, 0);
        return (
          <section key={key}>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-zinc-300">{formatDay(key)}</h2>
              <span className="tabular-nums text-xs text-zinc-500">
                合計 {sum.toLocaleString()} kcal
              </span>
            </div>
            <ul className="space-y-2">
              {list.map((m) => (
                <MealRow key={m.id} meal={m} onDelete={onDelete} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/* ---------- 体重 ---------- */
function WeightView({
  profile,
  weights,
  onAdd,
  onDelete,
  onSetTarget,
}: {
  profile: Profile;
  weights: WeightEntry[];
  onAdd: (kg: number) => void;
  onDelete: (id: string) => void;
  onSetTarget: (kg: number) => void;
}) {
  const [input, setInput] = useState("");
  const [editTarget, setEditTarget] = useState(false);
  const [targetInput, setTargetInput] = useState(String(profile.targetWeight));

  /* weights は新しい順。計算では古い順のほうが扱いやすい */
  const asc = useMemo(() => [...weights].sort((a, b) => a.ts - b.ts), [weights]);

  const current = weights.length > 0 ? weights[0].kg : profile.weight;
  const start = asc.length > 0 ? asc[0].kg : profile.weight;
  const target = profile.targetWeight;

  const bmi = calcBmi(current, profile.height);
  const category = bmiCategory(bmi);
  const std = standardWeight(profile.height);

  const changed = Math.round((current - start) * 10) / 10;
  const toGo = Math.round((current - target) * 10) / 10;
  const span = start - target;
  const progress =
    Math.abs(span) < 0.05
      ? 100
      : Math.max(0, Math.min(100, ((start - current) / span) * 100));

  /**
   * 増減ペース（kg/週）。記録が2件以上・1日以上離れている場合のみ。
   * 起点は「今日」ではなく最後に記録した日。しばらく記録していなくても直近の傾向が出せる。
   */
  const pace = useMemo(() => {
    if (asc.length < 2) return null;
    const since = asc[asc.length - 1].ts - 28 * 86400000;
    const recent = asc.filter((w) => w.ts >= since);
    if (recent.length < 2) return null;
    const first = recent[0];
    const last = recent[recent.length - 1];
    const days = (last.ts - first.ts) / 86400000;
    if (days < 1) return null;
    return ((last.kg - first.kg) / days) * 7;
  }, [asc]);

  /** 現在のペースを維持した場合の目標達成予定日（最後の記録日からの見込み）。 */
  const forecast = useMemo(() => {
    if (asc.length === 0) return null;
    if (pace === null || Math.abs(pace) < 0.05 || Math.abs(toGo) < 0.05) return null;
    // toGo>0 は減量が必要 → ペースが減少（負）なら近づいている
    if (toGo > 0 && pace >= 0) return null;
    if (toGo < 0 && pace <= 0) return null;
    const weeks = Math.abs(toGo / pace);
    if (weeks > 260) return null; // 5年以上先は現実的でないので出さない
    return new Date(asc[asc.length - 1].ts + weeks * 7 * 86400000);
  }, [asc, pace, toGo]);

  function submit() {
    const kg = Math.round(Number(input) * 10) / 10;
    if (!(kg >= 25 && kg <= 250)) return;
    onAdd(kg);
    setInput("");
  }

  return (
    <div className="space-y-5">
      {/* 現在の体重とBMI */}
      <section className="rounded-2xl border border-zinc-900 bg-zinc-950 p-5">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs text-zinc-500">現在の体重</p>
            <p className="mt-0.5 text-4xl font-bold tabular-nums">
              {current.toFixed(1)}
              <span className="ml-1 text-base font-normal text-zinc-500">kg</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-zinc-500">BMI</p>
            <p className="mt-0.5 text-2xl font-bold tabular-nums">{bmi.toFixed(1)}</p>
            <p className={`text-xs ${category.color}`}>{category.label}</p>
          </div>
        </div>
        {asc.length > 1 && (
          <p className="mt-2 text-xs text-zinc-500">
            記録開始から{" "}
            <span className={changed <= 0 ? "text-emerald-400" : "text-red-400"}>
              {changed > 0 ? "+" : ""}
              {changed.toFixed(1)} kg
            </span>
            （{start.toFixed(1)} kg から）
          </p>
        )}
        <p className="mt-1 text-[11px] text-zinc-600">
          身長 {profile.height}cm の標準体重（BMI22）は {std.toFixed(1)} kg
        </p>
      </section>

      {/* 目標までの進捗 */}
      <section className="rounded-2xl border border-zinc-900 bg-zinc-950 p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-zinc-300">目標まで</p>
          <button
            onClick={() => {
              setTargetInput(String(profile.targetWeight));
              setEditTarget((e) => !e);
            }}
            className="text-xs text-orange-400 active:text-orange-300"
          >
            {editTarget ? "やめる" : "目標を変更"}
          </button>
        </div>

        {editTarget ? (
          <div className="mt-3 flex gap-2">
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={targetInput}
              onChange={(e) => setTargetInput(e.target.value)}
              className="flex-1 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-center text-xl font-bold tabular-nums outline-none focus:border-orange-500"
            />
            <button
              onClick={() => {
                const kg = Math.round(Number(targetInput) * 10) / 10;
                if (kg >= 25 && kg <= 250) {
                  onSetTarget(kg);
                  setEditTarget(false);
                }
              }}
              className="rounded-xl bg-orange-600 px-5 font-semibold active:scale-[0.98]"
            >
              決定
            </button>
          </div>
        ) : (
          <>
            <p className="mt-1 text-3xl font-bold tabular-nums">
              {Math.abs(toGo) < 0.05 ? (
                <span className="text-emerald-400">達成！🎉</span>
              ) : (
                <>
                  あと {Math.abs(toGo).toFixed(1)}
                  <span className="ml-1 text-base font-normal text-zinc-500">
                    kg {toGo > 0 ? "減量" : "増量"}
                  </span>
                </>
              )}
            </p>
            <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[11px] text-zinc-600">
              <span>開始 {start.toFixed(1)}kg</span>
              <span>目標 {target.toFixed(1)}kg</span>
            </div>
          </>
        )}

        {pace !== null && (
          <p className="mt-3 rounded-lg bg-zinc-900 px-3 py-2 text-xs text-zinc-400">
            📈 直近4週間のペース:{" "}
            <span className={pace <= 0 ? "text-emerald-400" : "text-red-400"}>
              {pace > 0 ? "+" : ""}
              {pace.toFixed(2)} kg/週
            </span>
            {forecast && (
              <>
                <br />
                🎯 このペースなら{" "}
                <span className="text-orange-400">
                  {forecast.getFullYear()}年{forecast.getMonth() + 1}月{forecast.getDate()}日
                </span>{" "}
                ごろ達成
              </>
            )}
          </p>
        )}
      </section>

      {/* 推移グラフ */}
      <section className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
        <p className="mb-2 text-sm font-semibold text-zinc-300">体重の推移</p>
        {asc.length < 2 ? (
          <p className="py-8 text-center text-sm text-zinc-600">
            記録が2件以上たまるとグラフが出ます
          </p>
        ) : (
          <WeightChart points={asc} target={target} />
        )}
      </section>

      {/* 記録する */}
      <section className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
        <p className="mb-2 text-sm font-semibold text-zinc-300">今日の体重を記録</p>
        <div className="flex gap-2">
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={current.toFixed(1)}
            className="flex-1 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-center text-2xl font-bold tabular-nums outline-none focus:border-orange-500"
          />
          <button
            onClick={submit}
            disabled={!(Number(input) >= 25 && Number(input) <= 250)}
            className="rounded-xl bg-orange-600 px-6 font-semibold disabled:opacity-40 active:scale-[0.98]"
          >
            記録
          </button>
        </div>
        <p className="mt-2 text-[11px] text-zinc-600">
          記録すると目標カロリーも自動で再計算されます（設定で手動にしている場合を除く）
        </p>
      </section>

      {/* 記録一覧 */}
      {weights.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-zinc-400">記録</h2>
          <ul className="space-y-1.5">
            {weights.slice(0, 60).map((w, i) => {
              const prev = weights[i + 1];
              const diff = prev ? Math.round((w.kg - prev.kg) * 10) / 10 : null;
              return (
                <li
                  key={w.id}
                  className="flex items-center gap-3 rounded-xl border border-zinc-900 bg-zinc-950 px-3 py-2.5"
                >
                  <span className="w-24 shrink-0 text-xs text-zinc-500">
                    {formatDay(dayKey(w.ts))} {formatTime(w.ts)}
                  </span>
                  <span className="flex-1 tabular-nums font-semibold">{w.kg.toFixed(1)} kg</span>
                  {diff !== null && diff !== 0 && (
                    <span
                      className={`tabular-nums text-xs ${
                        diff < 0 ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {diff > 0 ? "+" : ""}
                      {diff.toFixed(1)}
                    </span>
                  )}
                  <button
                    onClick={() => {
                      if (confirm(`${w.kg.toFixed(1)}kg の記録を削除しますか？`)) onDelete(w.id);
                    }}
                    className="shrink-0 px-1 text-xs text-zinc-700 active:text-red-400"
                    aria-label="削除"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}

/** 体重推移の折れ線グラフ。外部ライブラリを使わずSVGで描く。 */
function WeightChart({ points, target }: { points: WeightEntry[]; target: number }) {
  const W = 320;
  const H = 150;
  const padL = 34;
  const padR = 10;
  const padT = 12;
  const padB = 22;

  const kgs = points.map((p) => p.kg);
  const lo = Math.min(...kgs, target);
  const hi = Math.max(...kgs, target);
  // 上下に少し余白を持たせる（全部同じ値でも潰れないよう最低1kgの幅を確保）
  const pad = Math.max(0.5, (hi - lo) * 0.15);
  const yMin = lo - pad;
  const yMax = hi + pad;

  const tMin = points[0].ts;
  const tMax = points[points.length - 1].ts;
  const tSpan = Math.max(1, tMax - tMin);

  const x = (ts: number) => padL + ((ts - tMin) / tSpan) * (W - padL - padR);
  const y = (kg: number) => padT + (1 - (kg - yMin) / (yMax - yMin)) * (H - padT - padB);

  const line = points.map((p) => `${x(p.ts).toFixed(1)},${y(p.kg).toFixed(1)}`).join(" ");
  const areaPath = `M ${x(tMin).toFixed(1)},${(H - padB).toFixed(1)} L ${line
    .split(" ")
    .join(" L ")} L ${x(tMax).toFixed(1)},${(H - padB).toFixed(1)} Z`;

  const last = points[points.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="体重推移グラフ">
      {/* 目標ライン */}
      <line
        x1={padL}
        x2={W - padR}
        y1={y(target)}
        y2={y(target)}
        stroke="#10b981"
        strokeWidth="1"
        strokeDasharray="4 3"
      />
      <text x={W - padR} y={y(target) - 4} textAnchor="end" fontSize="9" fill="#10b981">
        目標 {target.toFixed(1)}
      </text>

      {/* 面と折れ線 */}
      <path d={areaPath} fill="#f9731620" />
      <polyline points={line} fill="none" stroke="#f97316" strokeWidth="2" strokeLinejoin="round" />
      {points.map((p) => (
        <circle key={p.id} cx={x(p.ts)} cy={y(p.kg)} r="2" fill="#f97316" />
      ))}
      <circle cx={x(last.ts)} cy={y(last.kg)} r="3.5" fill="#fb923c" stroke="#000" strokeWidth="1" />

      {/* 目盛り */}
      <text x={padL - 5} y={padT + 4} textAnchor="end" fontSize="9" fill="#71717a">
        {yMax.toFixed(1)}
      </text>
      <text x={padL - 5} y={H - padB} textAnchor="end" fontSize="9" fill="#71717a">
        {yMin.toFixed(1)}
      </text>
      <text x={padL} y={H - 6} fontSize="9" fill="#71717a">
        {formatDay(dayKey(tMin))}
      </text>
      <text x={W - padR} y={H - 6} textAnchor="end" fontSize="9" fill="#71717a">
        {formatDay(dayKey(tMax))}
      </text>
    </svg>
  );
}

/* ---------- 設定 ---------- */
function SettingsView({
  profile,
  onSave,
  onLogout,
}: {
  profile: Profile;
  onSave: (p: Profile) => void;
  onLogout: () => void;
}) {
  const [form, setForm] = useState<FormState>({
    sex: profile.sex,
    age: String(profile.age),
    height: String(profile.height),
    weight: String(profile.weight),
    targetWeight: String(profile.targetWeight),
    activity: profile.activity,
    goal: profile.goal,
  });
  const [manual, setManual] = useState(!profile.autoTarget);
  const [manualKcal, setManualKcal] = useState(String(profile.targetKcal));

  const age = Number(form.age);
  const height = Number(form.height);
  const weight = Number(form.weight);
  const valid = age >= 10 && age <= 100 && height >= 100 && height <= 250 && weight >= 25 && weight <= 250;
  const auto = valid
    ? calcTargetKcal({ sex: form.sex, age, height, weight, activity: form.activity, goal: form.goal })
    : profile.targetKcal;

  return (
    <div className="pb-6">
      <ProfileForm form={form} setForm={setForm} />

      <div className="mt-6 rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm">目標カロリー</p>
          <button
            onClick={() => setManual((m) => !m)}
            className="text-xs text-orange-400 active:text-orange-300"
          >
            {manual ? "自動計算に戻す" : "手動で設定する"}
          </button>
        </div>
        {manual ? (
          <input
            type="number"
            inputMode="numeric"
            value={manualKcal}
            onChange={(e) => setManualKcal(e.target.value)}
            className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-center text-2xl font-bold tabular-nums outline-none focus:border-orange-500"
          />
        ) : (
          <p className="mt-2 text-center text-3xl font-bold text-orange-400">
            {auto.toLocaleString()}
            <span className="ml-1 text-base font-normal text-zinc-400">kcal</span>
          </p>
        )}
      </div>

      <button
        disabled={!valid}
        onClick={() =>
          onSave({
            sex: form.sex,
            age,
            height,
            weight,
            activity: form.activity,
            goal: form.goal,
            targetWeight: Number(form.targetWeight) > 0
              ? Math.round(Number(form.targetWeight) * 10) / 10
              : standardWeight(height),
            targetKcal: manual ? Math.max(800, Math.round(Number(manualKcal) || auto)) : auto,
            autoTarget: !manual,
          })
        }
        className="mt-5 w-full rounded-xl bg-orange-600 py-3.5 font-semibold disabled:opacity-40 active:scale-[0.98]"
      >
        保存する
      </button>

      <button
        onClick={() => {
          if (confirm("ロックしますか？（もう一度アクセスコードが必要になります）")) onLogout();
        }}
        className="mt-3 w-full py-3 text-xs text-zinc-600 active:text-zinc-400"
      >
        ロックする
      </button>
    </div>
  );
}
