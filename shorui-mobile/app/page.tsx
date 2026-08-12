"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Shot = { file: File; url: string };

const PW_KEY = "shorui_pw";

// この束のフォルダ名を1回だけ作る。1枚ずつ送ってもこのIDでPC側では1フォルダにまとまる。
function makeBatchId(property: string): string {
  const p = (n: number) => String(n).padStart(2, "0");
  const d = new Date();
  const stamp =
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  const slug =
    property.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_").trim().slice(0, 40) ||
    "未指定";
  return `${stamp}_${slug}`;
}

// 送信前に写真を縮小・JPEG化する。
// スマホ写真は1枚2〜4MBあり、数枚で Vercel のリクエスト上限(4.5MB)を超えて弾かれる。
// 長辺1600px・JPEG品質0.72に落とすと書類の文字は充分読めるまま1枚あたり数百KBに収まり、
// 10枚でも上限に収まる。HEICもJPEGに揃うのでPC側の読み取り・サムネも安定する。
async function shrinkForUpload(file: File): Promise<Blob> {
  const MAX_EDGE = 1600;
  const QUALITY = 0.72;
  // iOS Safari で確実な <img> 経由でデコードする（createImageBitmap は失敗しやすい）。
  // iOS は HEIC も <img> で読め、表示時に EXIF の向きを自動で正立させる。
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("decode failed"));
      im.src = url;
    });
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    if (!iw || !ih) return file;
    const scale = Math.min(1, MAX_EDGE / Math.max(iw, ih));
    const w = Math.max(1, Math.round(iw * scale));
    const h = Math.max(1, Math.round(ih * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, w, h);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", QUALITY)
    );
    // 縮小に失敗、または元よりむしろ大きくなった場合は原本を使う。
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function Home() {
  // --- パスワードゲート ---
  const [authPw, setAuthPw] = useState<string | null>(null); // 検証済みの合言葉
  const [pwInput, setPwInput] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(PW_KEY) : null;
    if (saved) setAuthPw(saved);
  }, []);

  const unlock = async () => {
    setChecking(true);
    setPwErr("");
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password: pwInput }),
      });
      if (!res.ok) throw new Error();
      localStorage.setItem(PW_KEY, pwInput);
      setAuthPw(pwInput);
      setPwInput("");
    } catch {
      setPwErr("パスワードが違います");
    } finally {
      setChecking(false);
    }
  };

  // --- 撮影・送信 ---
  const [property, setProperty] = useState("");
  const [memo, setMemo] = useState("");
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const next: Shot[] = [];
    for (const f of Array.from(list)) {
      if (f.type.startsWith("image/") || f.name.toLowerCase().endsWith(".heic")) {
        next.push({ file: f, url: URL.createObjectURL(f) });
      }
    }
    setShots((prev) => [...prev, ...next]);
    setMsg(null);
  }, []);

  const remove = (i: number) => {
    setShots((prev) => {
      URL.revokeObjectURL(prev[i].url);
      return prev.filter((_, idx) => idx !== i);
    });
  };

  const submit = async () => {
    if (shots.length === 0) {
      setMsg({ ok: false, text: "先に写真を撮ってください" });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      // 1枚ずつ別リクエストで送る（Vercelのリクエスト上限4.5MBを原理的に超えないため）。
      // 束IDを共有するので、PC側では今まで通り1つのフォルダにまとまる。
      const batch = makeBatchId(property);
      const total = shots.length;
      for (let i = 0; i < total; i++) {
        setMsg({ ok: true, text: `送信中… ${i + 1}/${total} 枚` });
        const blob = await shrinkForUpload(shots[i].file);
        const fd = new FormData();
        fd.append("password", authPw || "");
        fd.append("property", property);
        fd.append("memo", memo);
        fd.append("batch", batch);
        fd.append("index", String(i + 1));
        fd.append("total", String(total));
        if (i === total - 1) fd.append("writeMeta", "1"); // 付帯情報は最後の1回だけ
        // ファイル名はASCII固定（iOS Safari は非ASCIIファイル名で送信時に例外を投げる）。
        fd.append("files", blob, `shot_${String(i + 1).padStart(2, "0")}.jpg`);

        const res = await fetch("/api/upload", { method: "POST", body: fd });
        const text = await res.text();
        let j: { ok?: boolean; error?: string };
        try {
          j = text ? JSON.parse(text) : {};
        } catch {
          throw new Error(
            res.status === 413
              ? `${i + 1}枚目が大きすぎて送れませんでした。`
              : `送信に失敗しました（${res.status}）`
          );
        }
        if (res.status === 401) {
          localStorage.removeItem(PW_KEY);
          setAuthPw(null);
          throw new Error("パスワードが変わりました。もう一度入力してください。");
        }
        if (!res.ok || !j.ok) throw new Error(j.error || "送信に失敗しました");
      }
      shots.forEach((s) => URL.revokeObjectURL(s.url));
      setShots([]);
      setProperty("");
      setMemo("");
      setMsg({ ok: true, text: `送信しました（${total}枚）。PCのキャビネットで整理できます。` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "送信に失敗しました" });
    } finally {
      setBusy(false);
    }
  };

  // --- ロック画面 ---
  if (!authPw) {
    return (
      <div className="wrap gate">
        <h1>🗄 書類キャビネット 取込</h1>
        <p className="sub">パスワードを入力してください。</p>
        <input
          type="password"
          inputMode="numeric"
          value={pwInput}
          onChange={(e) => setPwInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && unlock()}
          placeholder="パスワード"
          autoFocus
        />
        {pwErr && <div className="toast err">{pwErr}</div>}
        <button className="btn" onClick={unlock} disabled={checking || !pwInput}>
          {checking ? "確認中…" : "開く"}
        </button>
      </div>
    );
  }

  // --- 本体 ---
  return (
    <div className="wrap">
      <h1>🗄 書類キャビネット 取込</h1>
      <p className="sub">
        クリアファイル1冊・箱1つの中身を数枚撮って送ると、Dropboxの「書類取込」に入ります。
        あとはPCのキャビネットがAIで目録化して整理します。
      </p>

      <label htmlFor="property">物件名・件名（任意）</label>
      <input
        id="property"
        type="text"
        value={property}
        onChange={(e) => setProperty(e.target.value)}
        placeholder="例: グランドメゾン天王寺 301号室"
      />
      <p className="hint">入れておくと、この束のフォルダ名に付いてPC側で見分けやすくなります。</p>

      <label htmlFor="memo">メモ（任意）</label>
      <textarea
        id="memo"
        value={memo}
        onChange={(e) => setMemo(e.target.value)}
        placeholder="例: 契約関係。棚に戻す前に撮影"
      />

      <label>写真</label>
      <label className="camera-label">
        📷 カメラで撮る / 写真を選ぶ（複数可）
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          onChange={(e) => {
            addFiles(e.target.files);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </label>

      {shots.length > 0 && (
        <>
          <div className="shots">
            {shots.map((s, i) => (
              <div className="shot" key={s.url}>
                <img src={s.url} alt={`shot ${i + 1}`} />
                <button className="rm" onClick={() => remove(i)} aria-label="削除">
                  ×
                </button>
              </div>
            ))}
          </div>
          <p className="count">{shots.length} 枚。もう一度「カメラで撮る」で追加できます。</p>
        </>
      )}

      {msg && <div className={`toast ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}

      <div className="bar">
        <div className="inner">
          <button className="btn" onClick={submit} disabled={busy}>
            {busy ? "送信中…" : `この束を送る${shots.length ? `（${shots.length}枚）` : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}
