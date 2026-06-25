import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { SpaceNode } from '../types';
import PanoramaViewer from '../PanoramaViewer';
import { loadProperty, updateProperty } from '../firebase';
import type { NodeMeta } from '../firebase';
import '../App.css';

function StatusDot({ status }: { status: SpaceNode['status'] }) {
  return <span className={`status-dot ${status}`} />;
}

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

// ── Update Modal ───────────────────────────────────────────────────────────────

interface UpdateModalProps {
  propertyId: string;
  name: string;
  address: string;
  nodes: SpaceNode[];
  existingNodeMeta: Record<string, NodeMeta>;
  deletedNodeIds: string[];
  pinPositions: Record<string, [number, number, number]>;
  displacement: number;
  onClose: () => void;
  onSaved: () => void;
}

function UpdateModal({
  propertyId, name, address, nodes, existingNodeMeta, deletedNodeIds,
  pinPositions, displacement, onClose, onSaved,
}: UpdateModalProps) {
  const [saving, setSaving] = useState(false);
  const [progress, setProgress] = useState({ msg: '', pct: 0 });
  const [done, setDone] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateProperty(
        propertyId, name, address,
        nodes.filter(n => n.status === 'done'),
        existingNodeMeta, deletedNodeIds,
        pinPositions, displacement,
        (msg, pct) => setProgress({ msg, pct }),
      );
      setDone(true);
      onSaved();
    } catch (e) {
      alert('保存中にエラーが発生しました: ' + (e instanceof Error ? e.message : e));
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={done ? undefined : onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        {!done ? (
          <>
            <div className="modal-title">変更を保存</div>
            <div className="modal-info">
              物件名: {name}<br />
              エリア数: {nodes.filter(n => n.status === 'done').length} 室
              {deletedNodeIds.length > 0 && `（${deletedNodeIds.length} 室削除）`}
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
              <button className="btn-modal-save" onClick={handleSave} disabled={saving}>
                {saving ? '保存中...' : '保存する'}
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="modal-success-icon">✓</div>
            <div className="modal-title">保存完了！</div>
            <div className="modal-actions">
              <button className="btn-modal-save" onClick={onClose}>閉じる</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── EditPage ──────────────────────────────────────────────────────────────────

export default function EditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [propName, setPropName] = useState('');
  const [propAddress, setPropAddress] = useState('');
  const [nodes, setNodes] = useState<SpaceNode[]>([]);
  const [existingNodeMeta, setExistingNodeMeta] = useState<Record<string, NodeMeta>>({});
  const [deletedNodeIds, setDeletedNodeIds] = useState<string[]>([]);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [displacement, setDisplacement] = useState(1.5);
  const [pinPositions, setPinPositions] = useState<Record<string, [number, number, number]>>({});
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  const workerRef = useRef<Worker | null>(null);
  const isProcessingRef = useRef(false);
  const queueRef = useRef<SpaceNode[]>([]);

  // Load existing property
  useEffect(() => {
    if (!id) { setLoadError('物件IDが指定されていません'); setLoading(false); return; }
    loadProperty(id)
      .then(d => {
        setPropName(d.name);
        setPropAddress(d.address);
        setNodes(d.nodes);
        setExistingNodeMeta(d.rawNodeData);
        setDisplacement(d.displacement);
        setPinPositions(d.pinPositions);
        setCurrentNodeId(d.nodes[0]?.id ?? null);
      })
      .catch(e => setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  // AI Worker for new nodes
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
      const id2 = canvas.getContext('2d')!.getImageData(0, 0, w, h);
      workerRef.current?.postMessage(
        { type: 'process', nodeId: node.id, imageName: node.name, imageData: id2.data.buffer, width: w, height: h },
        [id2.data.buffer]
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

  const handleRename = useCallback((nodeId: string, name: string) =>
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, name } : n)), []);

  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes(prev => {
      const remaining = prev.filter(n => n.id !== nodeId);
      if (existingNodeMeta[nodeId]) {
        setDeletedNodeIds(d => [...d, nodeId]);
      }
      return remaining;
    });
    setCurrentNodeId(prev => {
      if (prev !== nodeId) return prev;
      const remaining = nodes.filter(n => n.id !== nodeId && n.status === 'done');
      return remaining[0]?.id ?? null;
    });
    setPinPositions(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(k => {
        if (k.startsWith(nodeId + '::') || k.endsWith('::' + nodeId)) delete next[k];
      });
      return next;
    });
  }, [existingNodeMeta, nodes]);

  const handleNavigate = useCallback((nodeId: string) => setCurrentNodeId(nodeId), []);

  const handlePinPositionChange = useCallback((fromId: string, toId: string, pos: [number, number, number]) =>
    setPinPositions(prev => ({ ...prev, [`${fromId}::${toId}`]: pos })), []);

  const handlePinPositionReset = useCallback((fromId: string, toId: string) =>
    setPinPositions(prev => { const n = { ...prev }; delete n[`${fromId}::${toId}`]; return n; }), []);

  const currentNode = nodes.find(n => n.id === currentNodeId && n.status === 'done') ?? null;
  const otherDoneNodes = nodes.filter(n => n.id !== currentNodeId && n.status === 'done');
  const processingNode = nodes.find(n => n.status === 'processing');
  const queuedCount = nodes.filter(n => n.status === 'queued').length;
  const doneCount = nodes.filter(n => n.status === 'done').length;
  const canSave = doneCount > 0 && !processingNode && queuedCount === 0 && propName.trim().length > 0;

  if (loading) {
    return (
      <div className="viewer-page-loading">
        <div className="vp-hex-spin">⬡</div>
        <p>物件データを読み込み中...</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="viewer-page-error">
        <div className="vp-error-icon">⚠</div>
        <p className="vp-error-msg">{loadError}</p>
        <button className="vp-error-back" onClick={() => navigate('/')}>← 一覧に戻る</button>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <button className="btn-back" onClick={() => navigate('/')}>← 物件一覧</button>
        <div className="logo">⬡ THETA SPACE</div>
        <div className="header-sub">物件編集</div>
        <div className="header-name-edit">
          <input
            className="header-name-input"
            value={propName}
            onChange={e => setPropName(e.target.value)}
            placeholder="物件名"
          />
          <input
            className="header-addr-input"
            value={propAddress}
            onChange={e => setPropAddress(e.target.value)}
            placeholder="住所・備考"
          />
        </div>
        <button
          className="btn-publish"
          disabled={!canSave}
          onClick={() => setShowUpdateModal(true)}
        >
          ☁ 変更を保存
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
                    <button
                      className="btn-room-delete"
                      onClick={e => { e.stopPropagation(); handleDeleteNode(node.id); }}
                      title="このエリアを削除"
                    >×</button>
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
            />
          ) : (
            <div className="viewer-placeholder">
              <div className="placeholder-spinner">⬡</div>
              <p className="placeholder-text">左のサイドバーからエリアを選択してください</p>
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

      {showUpdateModal && id && (
        <UpdateModal
          propertyId={id}
          name={propName}
          address={propAddress}
          nodes={nodes}
          existingNodeMeta={existingNodeMeta}
          deletedNodeIds={deletedNodeIds}
          pinPositions={pinPositions}
          displacement={displacement}
          onClose={() => setShowUpdateModal(false)}
          onSaved={() => {}}
        />
      )}
    </div>
  );
}
