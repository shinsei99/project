import { useState, useEffect, useRef } from 'react';
import type { User } from '../types';
import { saveUser, deletePhoto, savePhoto, getPhoto } from '../db';
import { AGE_CATEGORIES, GENDER_OPTIONS, ageCategoryFromBirthYear } from '../joStandards';

interface Props {
  users: User[];
  selectedUserId: string | null;
  joCategory: string;
  onSelectUser: (id: string) => void;
  onJoCategoryChange: (cat: string) => void;
  onUsersChange: () => void;
}

export default function UserSidebar({ users, selectedUserId, joCategory, onSelectUser, onJoCategoryChange, onUsersChange }: Props) {
  const [showNewUser, setShowNewUser] = useState(false);
  const [newName, setNewName] = useState('');
  const [newGender, setNewGender] = useState<'男子' | '女子'>('男子');
  const [newBirth, setNewBirth] = useState('2012-01-01');
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let url: string | null = null;
    if (selectedUserId) {
      getPhoto(selectedUserId).then(blob => {
        if (blob) {
          url = URL.createObjectURL(blob);
          setPhotoUrl(url);
        } else {
          setPhotoUrl(null);
        }
      });
    }
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [selectedUserId]);

  const selectedUser = users.find(u => u.id === selectedUserId);

  async function handleAddUser() {
    setError('');
    if (!newName.trim()) { setError('名前を入力してください'); return; }
    if (users.some(u => u.name === newName.trim())) { setError('同じ名前が既に存在します'); return; }
    const user: User = {
      id: crypto.randomUUID().slice(0, 8),
      name: newName.trim(),
      gender: newGender,
      birthDate: newBirth,
      createdAt: new Date().toISOString(),
    };
    await saveUser(user);
    onUsersChange();
    onSelectUser(user.id);
    setNewName(''); setNewBirth('2012-01-01'); setShowNewUser(false);
  }

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedUserId) return;
    await savePhoto(selectedUserId, file);
    const url = URL.createObjectURL(file);
    setPhotoUrl(prev => { if (prev) URL.revokeObjectURL(prev); return url; });
  }

  async function handleDeletePhoto() {
    if (!selectedUserId) return;
    await deletePhoto(selectedUserId);
    setPhotoUrl(prev => { if (prev) URL.revokeObjectURL(prev); return null; });
  }

  const autoJo = selectedUser ? ageCategoryFromBirthYear(new Date(selectedUser.birthDate).getFullYear()) : '';

  return (
    <aside className="sidebar">
      <div>
        <div className="sidebar-section-title">👤 ユーザー</div>
        {users.length > 0 ? (
          <div className="form-group">
            <select value={selectedUserId ?? ''} onChange={e => onSelectUser(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '7px', border: '1px solid #d1d5db' }}>
              {users.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
        ) : (
          <p style={{ fontSize: '0.85rem', color: '#64748b' }}>ユーザーが登録されていません</p>
        )}
      </div>

      {selectedUser && (
        <div className="user-card">
          <div className="user-name">{selectedUser.name}</div>
          <div className="user-meta">{selectedUser.gender}・{new Date().getFullYear() - new Date(selectedUser.birthDate).getFullYear()}歳</div>
        </div>
      )}

      {selectedUserId && (
        <>
          <div>
            <div className="sidebar-section-title">📸 プロフィール写真</div>
            {photoUrl && (
              <div className="photo-wrap">
                <img src={photoUrl} alt="プロフィール" />
              </div>
            )}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => fileRef.current?.click()}>
                {photoUrl ? '変更' : 'アップロード'}
              </button>
              {photoUrl && (
                <button className="btn btn-danger btn-sm" onClick={handleDeletePhoto}>削除</button>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handlePhotoUpload} />
          </div>

          <div>
            <div className="sidebar-section-title">JO区分</div>
            <select
              value={joCategory}
              onChange={e => onJoCategoryChange(e.target.value)}
              style={{ width: '100%', padding: '7px', borderRadius: '7px', border: '1px solid #d1d5db', fontSize: '0.9rem' }}
            >
              {AGE_CATEGORIES.map(c => (
                <option key={c} value={c}>{c}{c === autoJo ? ' (自動)' : ''}</option>
              ))}
            </select>
          </div>
        </>
      )}

      <div className="divider" />

      <div>
        <button className="btn btn-secondary btn-full" style={{ fontSize: '0.88rem' }} onClick={() => setShowNewUser(v => !v)}>
          {showNewUser ? '▲ キャンセル' : '＋ 新規ユーザー登録'}
        </button>
        {showNewUser && (
          <div style={{ marginTop: '10px' }}>
            <div className="form-group">
              <label>名前</label>
              <input type="text" value={newName} onChange={e => setNewName(e.target.value)} placeholder="例: 山田太郎" />
            </div>
            <div className="form-group">
              <label>性別</label>
              <select value={newGender} onChange={e => setNewGender(e.target.value as '男子' | '女子')}>
                {GENDER_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>生年月日</label>
              <input type="date" value={newBirth} onChange={e => setNewBirth(e.target.value)} min="1990-01-01" max={new Date().toISOString().slice(0, 10)} />
            </div>
            {error && <p className="hint hint-error">{error}</p>}
            <button className="btn btn-primary btn-full" onClick={handleAddUser}>登録する</button>
          </div>
        )}
      </div>
    </aside>
  );
}
