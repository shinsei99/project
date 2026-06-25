"use client";

import { useState } from "react";
import Uploader from "@/components/Uploader";
import FloorPlanViewer from "@/components/FloorPlanViewer";

type Status = "idle" | "analyzing" | "done" | "error";

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (file: File) => {
    setError(null);
    setSvg(null);

    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(file);

    setStatus("analyzing");

    try {
      const formData = new FormData();
      formData.append("image", file);

      const res = await fetch("/api/analyze", { method: "POST", body: formData });
      const json = await res.json();

      if (!res.ok) throw new Error(json.error || "エラーが発生しました");

      setSvg(json.svg);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "不明なエラー");
      setStatus("error");
    }
  };

  const handleReset = () => {
    setStatus("idle");
    setPreview(null);
    setSvg(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">間取り図トレーサー</h1>
            <p className="text-xs text-gray-400 mt-0.5">AI が間取り図を白黒シンプル図面に引き直し</p>
          </div>
          {status !== "idle" && (
            <button onClick={handleReset} className="text-sm text-gray-500 hover:text-gray-700 underline">
              リセット
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {status === "idle" && (
          <div className="max-w-xl mx-auto">
            <Uploader onUpload={handleUpload} />
            <p className="text-center text-xs text-gray-400 mt-4">
              カラー・モノクロどちらの間取り図も対応。解析に10〜30秒かかります。
            </p>
          </div>
        )}

        {status === "analyzing" && (
          <div className="flex flex-col items-center gap-6 py-16">
            <div className="w-10 h-10 border-2 border-gray-800 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-600 text-sm">AIが間取り図を解析・SVG生成中...</p>
            {preview && (
              <div className="max-w-xs opacity-40">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={preview} alt="元の間取り図" className="rounded-lg shadow" />
              </div>
            )}
          </div>
        )}

        {status === "error" && (
          <div className="max-w-xl mx-auto text-center py-16">
            <p className="text-red-600 text-sm mb-4">{error}</p>
            <button
              onClick={handleReset}
              className="px-5 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-700"
            >
              もう一度試す
            </button>
          </div>
        )}

        {status === "done" && svg && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h2 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">元の間取り図</h2>
              {preview && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview} alt="元の間取り図" className="w-full rounded-xl border border-gray-200 shadow-sm" />
              )}
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">引き直し結果</h2>
              <FloorPlanViewer svg={svg} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
