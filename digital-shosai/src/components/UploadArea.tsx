"use client";

import { useRef, useState } from "react";
import { FileUp, FileText } from "lucide-react";

/**
 * PDFの選択エリア（ドラッグ＆ドロップ対応・複数選択可）。
 * iPhone では「ファイル」アプリが開き、Dropbox 等から複数まとめて選べる。
 */
export function UploadArea({
  disabled,
  multiple,
  onFiles,
  onReject,
}: {
  disabled?: boolean;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  /** PDF以外を選んだときの通知。**alert は使わない**（操作を止めるうえ唐突なので画面内に出す） */
  onReject?: (message: string) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const all = Array.from(list);
    const pdfs = all.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const rejected = all.length - pdfs.length;
    if (pdfs.length === 0) {
      onReject?.("PDFファイルが含まれていません。PDFを選んでください。");
      return;
    }
    if (rejected > 0) onReject?.(`PDF以外の ${rejected} 件は除きました。`);
    onFiles(pdfs);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      className={[
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-12 text-center transition",
        disabled
          ? "cursor-not-allowed border-slate-800 bg-slate-900/50 text-slate-500"
          : dragging
            ? "border-sky-500 bg-sky-950/30 text-sky-200"
            : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-600 hover:bg-slate-800/60",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = ""; // 同じファイルを続けて選べるようにする
        }}
      />
      {dragging ? <FileText className="h-8 w-8" /> : <FileUp className="h-8 w-8" />}
      <p className="font-semibold">
        {multiple ? "PDFをドラッグ＆ドロップ（何冊でも）" : "PDFをドラッグ＆ドロップ"}
      </p>
      <p className="text-sm opacity-80">
        またはタップしてファイルを選択（iPhoneでは「ファイル」アプリからDropboxを選べます）
      </p>
    </div>
  );
}
