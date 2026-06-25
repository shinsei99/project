import { useState, useEffect, useCallback } from 'react';
import './App.css';
import type { User, SwimRecord, Goal } from './types';
import { getUsers, getRecords, getGoals } from './db';
import { ageCategoryFromBirthYear } from './joStandards';
import UserSidebar from './components/UserSidebar';
import TabInput from './components/TabInput';
import TabHistory from './components/TabHistory';
import TabBest from './components/TabBest';
import TabGoal from './components/TabGoal';

type Tab = 'input' | 'history' | 'best' | 'goal';

export default function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [records, setRecords] = useState<SwimRecord[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('input');
  const [joCategory, setJoCategory] = useState('小学生');

  const loadUsers = useCallback(async () => {
    const us = await getUsers();
    setUsers(us);
    if (us.length > 0 && !selectedUserId) {
      setSelectedUserId(us[0].id);
    }
  }, [selectedUserId]);

  const loadRecords = useCallback(async () => {
    if (!selectedUserId) { setRecords([]); return; }
    setRecords(await getRecords(selectedUserId));
  }, [selectedUserId]);

  const loadGoals = useCallback(async () => {
    if (!selectedUserId) { setGoals([]); return; }
    setGoals(await getGoals(selectedUserId));
  }, [selectedUserId]);

  useEffect(() => { loadUsers(); }, []);
  useEffect(() => { loadRecords(); loadGoals(); }, [selectedUserId]);

  useEffect(() => {
    const user = users.find(u => u.id === selectedUserId);
    if (user) {
      const auto = ageCategoryFromBirthYear(new Date(user.birthDate).getFullYear());
      if (auto) setJoCategory(auto);
    }
  }, [selectedUserId, users]);

  const selectedUser = users.find(u => u.id === selectedUserId) ?? null;

  const TABS: { key: Tab; label: string }[] = [
    { key: 'input', label: '📝 記録入力' },
    { key: 'history', label: '📊 履歴' },
    { key: 'best', label: '🏆 ベスト' },
    { key: 'goal', label: '🎯 目標' },
  ];

  return (
    <div className="app">
      <header className="app-header">
        <span style={{ fontSize: '1.6rem' }}>🏊</span>
        <h1>水泳記録トラッカー</h1>
      </header>
      <div className="app-body">
        <UserSidebar
          users={users}
          selectedUserId={selectedUserId}
          joCategory={joCategory}
          onSelectUser={id => setSelectedUserId(id)}
          onJoCategoryChange={setJoCategory}
          onUsersChange={loadUsers}
        />
        <main className="main-content">
          {!selectedUser ? (
            <div className="empty-state">
              <div className="empty-icon">🏊</div>
              <p>左側のパネルからユーザーを登録・選択してください</p>
            </div>
          ) : (
            <>
              <div className="tabs">
                {TABS.map(t => (
                  <button
                    key={t.key}
                    className={`tab-btn${activeTab === t.key ? ' active' : ''}`}
                    onClick={() => setActiveTab(t.key)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              {activeTab === 'input' && (
                <TabInput
                  user={selectedUser}
                  records={records}
                  joCategory={joCategory}
                  onRecordsChange={loadRecords}
                />
              )}
              {activeTab === 'history' && (
                <TabHistory
                  user={selectedUser}
                  records={records}
                  onRecordsChange={loadRecords}
                />
              )}
              {activeTab === 'best' && (
                <TabBest
                  user={selectedUser}
                  records={records}
                  joCategory={joCategory}
                />
              )}
              {activeTab === 'goal' && (
                <TabGoal
                  user={selectedUser}
                  records={records}
                  goals={goals}
                  onGoalsChange={loadGoals}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
