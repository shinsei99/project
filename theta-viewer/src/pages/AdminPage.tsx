import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import type { SpaceNode } from '../types';
import PanoramaViewer from '../PanoramaViewer';
import { isConfigured, saveProperty } from '../firebase';
import '../App.css';

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
      <input ref={inputRef} type="file" accept="image/*" multiple
        style={{ display: 'none' }} onChange={e => accept(e.target.files)} />
      <span className="sidebar-add-icon">＋</span>
      <span>部屋を追加</span>
    </div>
  );
}

// ── Main Drop Zone ────────────────────────────────────────────────────────────

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
      <input ref={inputRef} type="file" accept="image/*" multiple
        style={{ display: 'none' }} onChange={e => accept(e.target.files)} />
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

// ── Save Modal ────────────────────────────────────────────────────────────────

interface SaveModalProps {
  nodes: SpaceNode[];
  pinPositions: Record<string, [number, number, number]>;
  hiddenLinks: Record<string, boolean>;
  displacement: number;
  onClose: () => void;
  onSaved: (id: string) => void;
}

function SaveModal({ nodes, pinPositions, hiddenLinks, displacement, onClose, onSaved }: SaveModalProps) {
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState({ msg: '', pct: 0 });
  const [savedId, setSavedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const savedUrl = savedId ? `https://daikyocorp.co.jp/vr/#/property/${savedId}` : '';

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const id = await saveProperty(
        name.trim(), address.trim(),
        nodes.filter(n => n.status === 'done'),
        pinPositions, hiddenLinks, displacement,
        (msg, pct) => setProgress({ msg, pct })
      );
      setSavedId(id);
      onSaved(id);
    } catch (e) {
      alert('保存中にエラーが発生しました: ' + (e instanceof Error ? e.message : e));
      setSaving(false);
    }
  };

  const copyUrl = () => {
    navigator.clipboard.writeText(savedUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="modal-backdrop" onClick={savedId ? undefined : onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        {!savedId ? (
          <>
            <div className="modal-title">物件として保存</div>
            <div className="modal-field">
              <label className="modal-label">物件名 *</label>
              <input
                className="modal-input"
                placeholder="例：渋谷区 Aマンション 302号室"
                value={name}
                onChange={e => setName(e.target.value)}
                disabled={saving}
                autoFocus
              />
            </div>
            <div className="modal-field">
              <label className="modal-label">住所・備考</label>
              <input
                className="modal-input"
                placeholder="例：東京都渋谷区〇〇1-2-3"
                value={address}
                onChange={e => setAddress(e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="modal-info">
              登録エリア数: {nodes.filter(n => n.status === 'done').length} 室
            </div>
            {saving && (
              <div className="modal-progress">
                <div className="modal-progress-msg">{progress.msg}</div>
                <div className="modal-progress-track">
                  <div className="modal-progress-fill" style={{ width: `${progress.pct}%` }} />
                </div>
                <div className="modal-progress-pct">{progress.pct}%</div>
              </div>
            )}
            <div className="modal-actions">
              <button className="btn-modal-cancel" onClick={onClose} disabled={saving}>
                キャンセル
              </button>
              <button
                className="btn-modal-save"
                onClick={handleSave}
                disabled={!name.trim() || saving || !isConfigured}
              >
                {saving ? '保存中...' : '保存して公開'}
              </button>
            </div>
            {!isConfigured && (
              <div className="modal-warn">
                ⚠ Firebase が設定されていません。保存機能を使うにはトップページの設定手順を確認してください。
              </div>
            )}
          </>
        ) : (
          <>
            <div className="modal-success-icon">✓</div>
            <div className="modal-title">公開完了！</div>
            <div className="modal-success-name">{name}</div>
            <div className="modal-label" style={{ textAlign: 'center', marginBottom: 8 }}>
              お客様に送るVR内覧URL
            </div>
            <div className="modal-url-box">
              <span className="modal-url-text">{savedUrl}</span>
              <button className={`btn-copy-url${copied ? ' copied' : ''}`} onClick={copyUrl}>
                {copied ? '✓' : '📋'}
              </button>
            </div>
            <div className="modal-actions">
              <a className="btn-modal-view" href={savedUrl} target="_blank" rel="noreferrer">
                内覧ページを確認 →
              </a>
              <button className="btn-modal-cancel" onClick={onClose}>閉じる</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── AdminPage ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const navigate = useNavigate();
  const [nodes, setNodes] = useState<SpaceNode[]>([]);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [displacement, setDisplacement] = useState(1.5);
  const [pinPositions, setPinPositions] = useState<Record<string, [number, number, number]>>({});
  const [hiddenLinks, setHiddenLinks] = useState<Record<string, boolean>>({});
  const [showSaveModal, setShowSaveModal] = useState(false);

  const workerRef = useRef<Worker | null>(null);
  const isProcessingRef = useRef(false);
  const queueRef = useRef<SpaceNode[]>([]);

  useEffect(() => {
    const worker = new Worker(new URL('../aiWorker.ts', import.meta.url), { type: 'module' });
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
    if (isProcessingRef.current || queueRef.current.length === 0) return;
    const node = queueRef.current.shift()!;
    isProcessingRef.current = true;
    setNodes(prev => prev.map(n => n.id === node.id
      ? { ...n, status: 'processing', progress: 0, message: '処理を開始します...' } : n));
    const img = new Image();
    img.onload = () => {
      const maxW = 512, scale = img.width > maxW ? maxW / img.width : 1;
      const w = Math.round(img.width * scale), h = Math.round(img.height * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d')!.drawImage(img, 0, 0, w, h);
      const id = canvas.getContext('2d')!.getImageData(0, 0, w, h);
      workerRef.current?.postMessage(
        { type: 'process', nodeId: node.id, imageName: node.name, imageData: id.data.buffer, width: w, height: h },
        [id.data.buffer]
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
        status: 'queued', progress: 0, message: '処理待ち...',
      }));
      queueRef.current.push(...newNodes);
      return [...prev, ...newNodes];
    });
    setTimeout(() => processNextInQueue(), 0);
  }, [processNextInQueue]);

  const handleRename = useCallback((id: string, name: string) =>
    setNodes(prev => prev.map(n => n.id === id ? { ...n, name } : n)), []);

  const handleNavigate = useCallback((nodeId: string) => setCurrentNodeId(nodeId), []);

  const handlePinPositionChange = useCallback((fromId: string, toId: string, pos: [number, number, number]) =>
    setPinPositions(prev => ({ ...prev, [`${fromId}::${toId}`]: pos })), []);

  const handlePinPositionReset = useCallback((fromId: string, toId: string) =>
    setPinPositions(prev => { const n = { ...prev }; delete n[`${fromId}::${toId}`]; return n; }), []);

  const handleHiddenLinksChange = useCallback((fromId: string, toId: string, hidden: boolean) =>
    setHiddenLinks(prev => {
      const n = { ...prev };
      if (hidden) n[`${fromId}::${toId}`] = true;
      else delete n[`${fromId}::${toId}`];
      return n;
    }), []);

  const currentNode = nodes.find(n => n.id === currentNodeId && n.status === 'done') ?? null;
  const otherDoneNodes = nodes.filter(n => n.id !== currentNodeId && n.status === 'done');
  const processingNode = nodes.find(n => n.status === 'processing');
  const queuedCount = nodes.filter(n => n.status === 'queued').length;
  const doneCount = nodes.filter(n => n.status === 'done').length;
  const canSave = doneCount > 0 && !processingNode && queuedCount === 0;

  return (
    <div className="app">
      <header className="app-header">
        <button className="btn-back" onClick={() => navigate('/')}>← 物件一覧</button>
        <div className="logo">⬡ THETA SPACE</div>
        <div className="header-sub">新規物件作成</div>
        <div className="header-stats">{doneCount}/{nodes.length} エリア完成</div>
        <button
          className="btn-publish"
          disabled={!canSave}
          onClick={() => setShowSaveModal(true)}
        >
          ☁ 物件として保存・公開
        </button>
      </header>

      <div className="app-body">
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
                <div className="room-thumb" style={{ backgroundImage: `url(${node.imageUrl})` }}>
                  {node.status !== 'done' && (
                    <div className="room-thumb-overlay"><StatusDot status={node.status} /></div>
                  )}
                </div>
                <div className="room-info">
                  <input className="room-name-input" value={node.name}
                    onChange={e => handleRename(node.id, e.target.value)}
                    onClick={e => e.stopPropagation()} />
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
              hiddenLinks={hiddenLinks}
              onHiddenLinksChange={handleHiddenLinksChange}
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
              {queuedCount > 0 && <span className="bottom-bar-queue">残り {queuedCount} 件</span>}
            </div>
          </div>
        </div>
      )}

      {showSaveModal && (
        <SaveModal
          nodes={nodes}
          pinPositions={pinPositions}
          hiddenLinks={hiddenLinks}
          displacement={displacement}
          onClose={() => setShowSaveModal(false)}
          onSaved={() => { /* URL is shown inside modal */ }}
        />
      )}
    </div>
  );
}
