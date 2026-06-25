"use client";

import { useCallback, useState } from "react";

interface UploaderProps {
  onUpload: (file: File) => void;
  disabled?: boolean;
}

export default function Uploader({ onUpload, disabled }: UploaderProps) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onUpload(file);
    },
    [onUpload]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  };

  return (
    <label
      className={`flex flex-col items-center justify-center w-full h-56 border-2 border-dashed rounded-xl cursor-pointer transition-colors
        ${dragging ? "border-gray-800 bg-gray-100" : "border-gray-300 bg-gray-50 hover:bg-gray-100"}
        ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      <p className="text-sm text-gray-500">
        <span className="font-semibold text-gray-700">クリックして選択</span> またはドラッグ&ドロップ
      </p>
      <p className="text-xs text-gray-400 mt-1">JPEG / PNG / WebP</p>
      <input type="file" className="hidden" accept="image/jpeg,image/png,image/webp" onChange={handleChange} />
    </label>
  );
}
