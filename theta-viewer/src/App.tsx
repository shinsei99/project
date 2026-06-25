import { useState, useRef, useCallback, useEffect } from 'react';
import type { SpaceNode } from './types';
import PanoramaViewer from './PanoramaViewer';
import './App.css';

// ── Status Dot ────────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: SpaceNode['status'] }) {
  return <span className={`status-dot ${status}`} />;
}

// ── Sidebar Drop Zone ─────────────────────────────────────────────────────────

function SidebarDropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [hover, setHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = (files: FileList | null) => {
    if (!files) return;
    const imgs = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (imgs.length) onFiles(imgs);
  };

  return (
    <div
      className={`sidebar-dropzone ${hover ? 'hover' : ''}`}
      onDragOver={e => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={e => { e.preventDefault(); setHover(false); accept(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: 'none' }}
        onChange={e => accept(e.target.files)}
      />
      <span className="sidebar-add-icon">＋</span>
      <span>部屋を追加</span>
    </div>
  );
}

// ── Initial Drop Zone (empty state) ──────────────────────────────────────────

function MainDropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [hover, setHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = (files: FileList | null) => {
    if (!files) return;
    const imgs = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (imgs.length) onFiles(imgs);
  };

  return (
    <div
      className={`main-dropzone ${hover ? 'hover' : ''}`}
      onDragOver={e => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={e => { e.preventDefault(); setHover(false); accept(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: 'none' }}
        onChange={e => accept(e.target.files)}
      />
      <div className="main-dropzone-hex">⬡</div>
      <div className="main-dropzone-title">THETA パノラマ画像をドロップ</div>
      <div className="main-dropzone-sub">複数選択可能 · JPG / PNG · クリックでも選択</div>
      <div className="main-dropzone-tip">
        各部屋で撮影したパノラマ画像を一括アップロードすると<br />
        AIが奥行きを解析してMatterport風の3D空間に変換します
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [nodes, setNodes] = useState<SpaceNode[]>([]);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [displacement, setDisplacement] = useState(1.5);
  const [pinPositions, setPinPositions] = useState<Record<string, [number, number, number]>>({});

  const workerRef = useRef<Worker | null>(null);
  const isProcessingRef = useRef(false);
  const queueRef = useRef<SpaceNode[]>([]);

  // Init worker
  useEffect(() => {
    const worker = new Worker(new URL('./aiWorker.ts', import.meta.url), { type: 'module' });
    workerRef.current = worker;

    worker.onmessage = (e) => {
      const { type, nodeId } = e.data;

      if (type === 'progress') {
        setNodes(prev => prev.map(n =>
          n.id === nodeId ? { ...n, progress: e.data.progress, message: e.data.message } : n
        ));
      } else if (type === 'done') {
        const dm = new Float32Array(e.data.depthMap);
        setNodes(prev => prev.map(n =>
          n.id === nodeId
            ? { ...n, status: 'done', progress: 100, message: '完了', depthMap: dm, depthWidth: e.data.depthWidth, depthHeight: e.data.depthHeight }
            : n
        ));
        // Auto-select first completed node
        setCurrentNodeId(prev => prev ?? nodeId);
        isProcessingRef.current = false;
        processNextInQueue();
      } else if (type === 'error') {
        setNodes(prev => prev.map(n =>
          n.id === nodeId ? { ...n, status: 'error', message: e.data.message } : n
        ));
        isProcessingRef.current = false;
        processNextInQueue();
      }
    };

    return () => worker.terminate();
  }, []);

  const processNextInQueue = useCallback(() => {
    if (isProcessingRef.current) return;
    if (queueRef.current.length === 0) return;

    const node = queueRef.current.shift()!;
    isProcessingRef.current = true;

    setNodes(prev => prev.map(n => n.id === node.id ? { ...n, status: 'processing', progress: 0, message: '処理を開始します...' } : n));

    const maxW = 512;
    const img = new Image();
    img.onload = () => {
      const scale = img.width > maxW ? maxW / img.width : 1;
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d')!.drawImage(img, 0, 0, w, h);
      const imageData = canvas.getContext('2d')!.getImageData(0, 0, w, h);
      workerRef.current?.postMessage(
        { type: 'process', nodeId: node.id, imageName: node.name, imageData: imageData.data.buffer, width: w, height: h },
        [imageData.data.buffer]
      );
    };
    img.src = node.imageUrl;
  }, []);

  const handleFiles = useCallback((files: File[]) => {
    setNodes(prev => {
      const existingCount = prev.length;
      const newNodes: SpaceNode[] = files.map((file, i) => ({
        id: crypto.randomUUID(),
        name: `エリア ${existingCount + i + 1}`,
        imageUrl: URL.createObjectURL(file),
        status: 'queued',
        progress: 0,
        message: '処理待ち...',
      }));
      queueRef.current.push(...newNodes);
      return [...prev, ...newNodes];
    });

    setTimeout(() => processNextInQueue(), 0);
  }, [processNextInQueue]);

  const handleRename = useCallback((id: string, name: string) => {
    setNodes(prev => prev.map(n => n.id === id ? { ...n, name } : n));
  }, []);

  const handleNavigate = useCallback((nodeId: string) => {
    setCurrentNodeId(nodeId);
  }, []);

  const handlePinPositionChange = useCallback((fromId: string, toId: string, pos: [number, number, number]) => {
    setPinPositions(prev => ({ ...prev, [`${fromId}::${toId}`]: pos }));
  }, []);

  const handlePinPositionReset = useCallback((fromId: string, toId: string) => {
    setPinPositions(prev => {
      const next = { ...prev };
      delete next[`${fromId}::${toId}`];
      return next;
    });
  }, []);

  const currentNode = nodes.find(n => n.id === currentNodeId && n.status === 'done') ?? null;
  const otherDoneNodes = nodes.filter(n => n.id !== currentNodeId && n.status === 'done');
  const processingNode = nodes.find(n => n.status === 'processing');
  const queuedCount = nodes.filter(n => n.status === 'queued').length;

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="logo">⬡ THETA SPACE</div>
        <div className="header-sub">Multi-Room 3D Viewer · AI Powered</div>
        <div className="header-stats">
          {nodes.filter(n => n.status === 'done').length}/{nodes.length} エリア完成
        </div>
      </header>

      {/* Body */}
      <div className="app-body">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <span className="sidebar-title">ROOMS</span>
            <span className="room-badge">{nodes.length}</span>
          </div>

          <div className="room-list">
            {nodes.map(node => (
              <div
                key={node.id}
                className={`room-card${node.id === currentNodeId ? ' active' : ''}${node.status === 'error' ? ' error' : ''}${node.status !== 'done' ? ' disabled' : ''}`}
                onClick={() => { if (node.status === 'done') setCurrentNodeId(node.id); }}
              >
                {/* Thumbnail */}
                <div
                  className="room-thumb"
                  style={{ backgroundImage: `url(${node.imageUrl})` }}
                >
                  {node.status !== 'done' && (
                    <div className="room-thumb-overlay">
                      <StatusDot status={node.status} />
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="room-info">
                  <input
                    className="room-name-input"
                    value={node.name}
                    onChange={e => handleRename(node.id, e.target.value)}
                    onClick={e => e.stopPropagation()}
                  />
                  <div className="room-status-row">
                    <StatusDot status={node.status} />
                    <span className="room-status-text">
                      {node.status === 'queued' && '処理待ち'}
                      {node.status === 'processing' && `${node.progress}%`}
                      {node.status === 'done' && '準備完了'}
                      {node.status === 'error' && 'エラー'}
                    </span>
                  </div>
                  {node.status === 'processing' && (
                    <div className="room-mini-bar">
                      <div className="room-mini-fill" style={{ width: `${node.progress}%` }} />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <SidebarDropZone onFiles={handleFiles} />
        </aside>

        {/* Viewer area */}
        <div className="viewer-area">
          {currentNode ? (
            <PanoramaViewer
              currentNode={currentNode}
              otherNodes={otherDoneNodes}
              displacement={displacement}
              onDisplacementChange={setDisplacement}
              onNavigate={handleNavigate}
              pinPositions={pinPositions}
              onPinPositionChange={handlePinPositionChange}
              onPinPositionReset={handlePinPositionReset}
            />
          ) : nodes.length === 0 ? (
            <MainDropZone onFiles={handleFiles} />
          ) : (
            <div className="viewer-placeholder">
              <div className="placeholder-spinner">⬡</div>
              <p className="placeholder-text">AIが空間をスキャン中...</p>
              <p className="placeholder-sub">処理が完了したエリアから閲覧できます</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom progress bar */}
      {processingNode && (
        <div className="bottom-bar">
          <div className="bottom-bar-inner">
            <div className="bottom-bar-left">
              <span className="bottom-bar-badge">AI処理中</span>
              <span className="bottom-bar-name">{processingNode.name}</span>
            </div>
            <div className="bottom-bar-center">
              <div className="bottom-bar-message">{processingNode.message}</div>
              <div className="bottom-bar-track">
                <div className="bottom-bar-fill" style={{ width: `${processingNode.progress}%` }} />
              </div>
            </div>
            <div className="bottom-bar-right">
              <span className="bottom-bar-pct">{processingNode.progress}%</span>
              {queuedCount > 0 && (
                <span className="bottom-bar-queue">残り {queuedCount} 件</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
