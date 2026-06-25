"use client";

interface FloorPlanViewerProps {
  svg: string;
}

export default function FloorPlanViewer({ svg }: FloorPlanViewerProps) {
  const handleDownloadSVG = () => {
    const blob = new Blob([svg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "floor-plan.svg";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPNG = async () => {
    const img = new Image();
    const blob = new Blob([svg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 800;
      canvas.height = 800;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, 800, 800);
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((pngBlob) => {
        if (!pngBlob) return;
        const pngUrl = URL.createObjectURL(pngBlob);
        const a = document.createElement("a");
        a.href = pngUrl;
        a.download = "floor-plan.png";
        a.click();
        URL.revokeObjectURL(pngUrl);
      }, "image/png");
      URL.revokeObjectURL(url);
    };
    img.src = url;
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="w-full bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div
          className="w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
          style={{ lineHeight: 0 }}
        />
      </div>
      <div className="flex gap-3">
        <button
          onClick={handleDownloadSVG}
          className="px-5 py-2 bg-gray-800 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors"
        >
          SVGダウンロード
        </button>
        <button
          onClick={handleDownloadPNG}
          className="px-5 py-2 bg-white text-gray-800 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          PNGダウンロード
        </button>
      </div>
    </div>
  );
}
