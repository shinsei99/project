import { pipeline, env, RawImage } from '@huggingface/transformers';

env.allowLocalModels = false;
env.useBrowserCache = true;

let srPipeline: Awaited<ReturnType<typeof pipeline>> | null = null;
let depthPipeline: Awaited<ReturnType<typeof pipeline>> | null = null;
let srInitDone = false;
let depthInitDone = false;

async function imageDataToObjectURL(data: Uint8ClampedArray<ArrayBuffer>, w: number, h: number): Promise<string> {
  const canvas = new OffscreenCanvas(w, h);
  canvas.getContext('2d')!.putImageData(new ImageData(data, w, h), 0, 0);
  const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.92 });
  return URL.createObjectURL(blob);
}

async function rawImageToObjectURL(img: RawImage): Promise<string> {
  const channels = img.channels;
  const rgba = new Uint8ClampedArray(img.width * img.height * 4);
  for (let i = 0; i < img.width * img.height; i++) {
    rgba[i * 4]     = img.data[i * channels];
    rgba[i * 4 + 1] = img.data[i * channels + 1];
    rgba[i * 4 + 2] = img.data[i * channels + 2];
    rgba[i * 4 + 3] = 255;
  }
  return imageDataToObjectURL(rgba, img.width, img.height);
}

self.onmessage = async (e: MessageEvent) => {
  const { type, nodeId, imageName, imageData, width, height } = e.data;
  if (type !== 'process') return;

  const post = (msg: object) => self.postMessage({ ...msg, nodeId });

  try {
    // ── Step 1: Super Resolution model load ──────────────────────────────────
    if (!srInitDone) {
      srInitDone = true;
      post({ type: 'progress', progress: 0, message: `超解像モデルをダウンロード中...` });
      try {
        srPipeline = await pipeline(
          'image-to-image',
          'Xenova/swin2SR-classical-sr-x2-64',
          {
            progress_callback: (info: { status: string; progress?: number }) => {
              if (info.status === 'progress' && info.progress != null) {
                post({ type: 'progress', progress: Math.round(info.progress * 0.3), message: `超解像モデルをダウンロード中... ${Math.round(info.progress)}%` });
              }
            },
          } as Parameters<typeof pipeline>[2]
        );
      } catch {
        srPipeline = null; // Fallback: skip SR
      }
    }

    // ── Step 2: Depth estimation model load ──────────────────────────────────
    if (!depthInitDone) {
      depthInitDone = true;
      post({ type: 'progress', progress: 30, message: `深度推定モデルをダウンロード中...` });
      depthPipeline = await pipeline(
        'depth-estimation',
        'onnx-community/Depth-Anything-V2-Small-ONNX',
        {
          progress_callback: (info: { status: string; progress?: number }) => {
            if (info.status === 'progress' && info.progress != null) {
              post({ type: 'progress', progress: 30 + Math.round(info.progress * 0.3), message: `深度推定モデルをダウンロード中... ${Math.round(info.progress)}%` });
            }
          },
        } as Parameters<typeof pipeline>[2]
      );
    }

    // ── Step 3: Super resolution (small crop → 2x) ───────────────────────────
    post({ type: 'progress', progress: 60, message: `「${imageName}」を高解像度化中...` });

    let depthInputUrl: string;
    const originalRgba = new Uint8ClampedArray(imageData as ArrayBuffer);
    const originalUrl = await imageDataToObjectURL(originalRgba, width, height);

    if (srPipeline) {
      try {
        // Downscale to small input for SR (128x64 for panorama aspect)
        const srW = Math.min(128, width);
        const srH = Math.round(srW * (height / width));
        const srCanvas = new OffscreenCanvas(srW, srH);
        const fullCanvas = new OffscreenCanvas(width, height);
        fullCanvas.getContext('2d')!.putImageData(new ImageData(originalRgba, width, height), 0, 0);
        const bmp = await createImageBitmap(fullCanvas);
        srCanvas.getContext('2d')!.drawImage(bmp, 0, 0, srW, srH);
        const srBlob = await srCanvas.convertToBlob({ type: 'image/jpeg', quality: 0.9 });
        const srInputUrl = URL.createObjectURL(srBlob);

        post({ type: 'progress', progress: 65, message: `「${imageName}」を高解像度化中... 処理中` });
        const srResult = await (srPipeline as any)(srInputUrl);
        URL.revokeObjectURL(srInputUrl);

        const srImage: RawImage = srResult?.image ?? srResult;
        if (srImage?.width) {
          depthInputUrl = await rawImageToObjectURL(srImage);
        } else {
          depthInputUrl = originalUrl;
        }
      } catch {
        depthInputUrl = originalUrl;
      }
    } else {
      depthInputUrl = originalUrl;
    }

    // ── Step 4: Depth estimation ─────────────────────────────────────────────
    post({ type: 'progress', progress: 75, message: `「${imageName}」の空間をスキャン中...` });

    const depthResult = await (depthPipeline as any)(depthInputUrl);

    URL.revokeObjectURL(depthInputUrl);
    URL.revokeObjectURL(originalUrl);

    post({ type: 'progress', progress: 98, message: `「${imageName}」の3D空間を構築中...` });

    const depthMap = depthResult.depth.data as Float32Array;
    const depthWidth = depthResult.depth.width as number;
    const depthHeight = depthResult.depth.height as number;

    const buf = depthMap.buffer as ArrayBuffer;
    self.postMessage(
      { type: 'done', nodeId, depthMap: buf, depthWidth, depthHeight },
      { transfer: [buf] }
    );
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    post({ type: 'error', message });
  }
};
