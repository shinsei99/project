import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { listProperties, deleteProperty } from '../firebase';
import type { PropertySummary } from '../firebase';

const BASE = window.location.origin + window.location.pathname;

function viewerUrl(id: string) {
  return `${BASE}#/property/${id}`;
}

export default function PropertyListPage() {
  const navigate = useNavigate();
  const [properties, setProperties] = useState<PropertySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setProperties(await listProperties());
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const copyUrl = (id: string) => {
    navigator.clipboard.writeText(viewerUrl(id));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDelete = async (p: PropertySummary) => {
    if (!confirm(`「${p.name}」を削除しますか？\nこの操作は取り消せません。`)) return;
    setDeletingId(p.id);
    await deleteProperty(p.id, p.nodeOrder);
    await load();
    setDeletingId(null);
  };

  return (
    <div className="list-page">
      <header className="list-header">
        <div className="logo">⬡ THETA SPACE</div>
        <div className="header-sub">VR内覧 管理画面</div>
        <button className="btn-new" onClick={() => navigate('/admin')}>
          ＋ 新規物件を作成
        </button>
      </header>

      <main className="list-main">
        {loading ? (
          <div className="list-loading">
            <div className="loading-hex">⬡</div>
            <p>読み込み中...</p>
          </div>
        ) : properties.length === 0 ? (
          <div className="list-empty">
            <div className="empty-icon">⬡</div>
            <p className="empty-title">物件がまだありません</p>
            <p className="empty-sub">「新規物件を作成」から THETA 画像をアップロードして保存してください</p>
            <button className="btn-primary" onClick={() => navigate('/admin')}>
              ＋ 最初の物件を作成
            </button>
          </div>
        ) : (
          <div className="property-table-wrap">
            <table className="property-table">
              <thead>
                <tr>
                  <th>物件名</th>
                  <th>住所・備考</th>
                  <th>部屋数</th>
                  <th>登録日</th>
                  <th>VR内覧URL</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {properties.map(p => (
                  <tr key={p.id} className={deletingId === p.id ? 'deleting' : ''}>
                    <td className="prop-name" onClick={() => window.open(viewerUrl(p.id), '_blank')}>
                      {p.name}
                    </td>
                    <td className="prop-addr">{p.address || '—'}</td>
                    <td className="prop-rooms">{p.roomCount} 室</td>
                    <td className="prop-date">
                      {p.createdAt.toLocaleDateString('ja-JP')}
                    </td>
                    <td className="prop-url">
                      <button
                        className={`btn-copy${copiedId === p.id ? ' copied' : ''}`}
                        onClick={() => copyUrl(p.id)}
                      >
                        {copiedId === p.id ? '✓ コピー済み' : '🔗 URLをコピー'}
                      </button>
                      <a
                        className="btn-view"
                        href={viewerUrl(p.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        内覧 →
                      </a>
                    </td>
                    <td className="prop-actions">
                      <button
                        className="btn-edit"
                        onClick={() => navigate(`/edit/${p.id}`)}
                        disabled={deletingId === p.id}
                      >
                        編集
                      </button>
                      <button
                        className="btn-delete"
                        onClick={() => handleDelete(p)}
                        disabled={deletingId === p.id}
                      >
                        {deletingId === p.id ? '削除中...' : '削除'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
