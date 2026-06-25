import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { loadProperty, isConfigured } from '../firebase';
import type { PropertyViewData } from '../firebase';
import type { SpaceNode } from '../types';
import PanoramaViewer from '../PanoramaViewer';

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<PropertyViewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (!id) { setError('物件IDが指定されていません'); setLoading(false); return; }
    if (!isConfigured) { setError('Supabase が設定されていません'); setLoading(false); return; }
    loadProperty(id)
      .then(d => {
        setData(d);
        setCurrentNodeId(d.nodes[0]?.id ?? null);
      })
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  const handleNavigate = useCallback((nodeId: string) => setCurrentNodeId(nodeId), []);

  if (loading) {
    return (
      <div className="viewer-page-loading">
        <div className="vp-hex-spin">⬡</div>
        <p>VR空間を読み込み中...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="viewer-page-error">
        <div className="vp-error-icon">⚠</div>
        <p className="vp-error-msg">{error ?? '物件データを取得できませんでした'}</p>
        <a href={window.location.origin + window.location.pathname} className="vp-error-back">
          ← トップへ戻る
        </a>
      </div>
    );
  }

  const currentNode = data.nodes.find(n => n.id === currentNodeId) ?? data.nodes[0] ?? null;
  const otherNodes = data.nodes.filter(n => n.id !== currentNode?.id);

  return (
    <div className="viewer-page">
      <header className="vp-header">
        <div className="vp-logo">⬡ VR内覧</div>
        <div className="vp-prop-name">{data.name}</div>
        {data.address && <div className="vp-address">{data.address}</div>}
      </header>

      <div className="vp-body">
        {currentNode ? (
          <PanoramaViewer
            currentNode={currentNode}
            otherNodes={otherNodes}
            displacement={data.displacement}
            onDisplacementChange={() => {}}
            onNavigate={handleNavigate}
            pinPositions={data.pinPositions}
            onPinPositionChange={() => {}}
            onPinPositionReset={() => {}}
            readOnly
          />
        ) : (
          <div className="viewer-placeholder">
            <p>空間データがありません</p>
          </div>
        )}
      </div>

      {data.nodes.length > 1 && (
        <nav className="vp-room-nav">
          {data.nodes.map((node: SpaceNode) => (
            <button
              key={node.id}
              className={`vp-room-btn${node.id === currentNode?.id ? ' active' : ''}`}
              onClick={() => handleNavigate(node.id)}
            >
              <div
                className="vp-room-thumb"
                style={{ backgroundImage: `url(${node.imageUrl})` }}
              />
              <span className="vp-room-label">{node.name}</span>
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
