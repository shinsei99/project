import type { SpaceNode } from './types';

const HTTP_BASE = 'https://daikyocorp.co.jp/vr';
const API_BASE  = 'http://localhost:8519';

export const isConfigured = true;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PropertySummary {
  id: string;
  name: string;
  address: string;
  createdAt: Date;
  roomCount: number;
  nodeOrder: string[];
}

export interface NodeMeta {
  name: string;
  imageUrl: string;
  depthUrl: string;
  depthWidth: number;
  depthHeight: number;
}

export interface PropertyViewData {
  id: string;
  name: string;
  address: string;
  nodes: SpaceNode[];
  pinPositions: Record<string, [number, number, number]>;
  displacement: number;
  rawNodeData: Record<string, NodeMeta>;
}

// ── List ──────────────────────────────────────────────────────────────────────

export async function listProperties(): Promise<PropertySummary[]> {
  const res = await fetch(`${HTTP_BASE}/index.json`, { cache: 'no-store' });
  if (!res.ok) return [];
  const data: Array<{ id: string; name: string; address: string; createdAt: string; roomCount: number }> = await res.json();
  return data.map(r => ({
    id: r.id,
    name: r.name ?? '（名称未設定）',
    address: r.address ?? '',
    createdAt: new Date(r.createdAt),
    roomCount: r.roomCount,
    nodeOrder: [],
  }));
}

// ── Load ──────────────────────────────────────────────────────────────────────

export async function loadProperty(propertyId: string): Promise<PropertyViewData> {
  const res = await fetch(`${HTTP_BASE}/${propertyId}/meta.json`, { cache: 'no-store' });
  if (!res.ok) throw new Error('物件が見つかりません (ID: ' + propertyId + ')');
  const meta = await res.json() as {
    id: string; name: string; address: string;
    displacement: number;
    pinPositions: Record<string, [number, number, number]>;
    nodes: Array<{ id: string; name: string; imageUrl: string; depthUrl: string; depthWidth: number; depthHeight: number }>;
  };

  const nodes: SpaceNode[] = [];
  const rawNodeData: Record<string, NodeMeta> = {};

  for (const n of meta.nodes) {
    const depthRes = await fetch(n.depthUrl, { cache: 'no-store' });
    if (!depthRes.ok) throw new Error(`深度データの取得に失敗しました: ${n.name}`);
    const depthMap = new Float32Array(await depthRes.arrayBuffer());
    nodes.push({
      id: n.id, name: n.name, imageUrl: n.imageUrl,
      status: 'done', progress: 100, message: '',
      depthMap, depthWidth: n.depthWidth, depthHeight: n.depthHeight,
    });
    rawNodeData[n.id] = { name: n.name, imageUrl: n.imageUrl, depthUrl: n.depthUrl, depthWidth: n.depthWidth, depthHeight: n.depthHeight };
  }

  return {
    id: meta.id, name: meta.name, address: meta.address ?? '',
    nodes, pinPositions: meta.pinPositions ?? {}, displacement: meta.displacement ?? 1.5,
    rawNodeData,
  };
}

// ── Save ──────────────────────────────────────────────────────────────────────

export async function saveProperty(
  name: string,
  address: string,
  nodes: SpaceNode[],
  pinPositions: Record<string, [number, number, number]>,
  displacement: number,
  onProgress: (msg: string, pct: number) => void,
): Promise<string> {
  onProgress('物件を初期化中...', 2);
  const initRes = await fetch(`${API_BASE}/api/property/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, address }),
  });
  if (!initRes.ok) throw new Error(await initRes.text());
  const { id } = await initRes.json() as { id: string };

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const pct = 5 + Math.round((i / nodes.length) * 85);
    onProgress(`「${node.name}」をアップロード中...`, pct);

    const imageBlob = await fetch(node.imageUrl).then(r => r.blob());
    const depthArr = node.depthMap!;
    const depthCopy = depthArr.buffer.slice(depthArr.byteOffset, depthArr.byteOffset + depthArr.byteLength) as ArrayBuffer;
    const depthBlob = new Blob([depthCopy], { type: 'application/octet-stream' });

    const form = new FormData();
    form.append('nodeId', node.id);
    form.append('name', node.name);
    form.append('depthWidth', String(node.depthWidth!));
    form.append('depthHeight', String(node.depthHeight!));
    form.append('image', imageBlob, `${node.id}-image.jpg`);
    form.append('depth', depthBlob, `${node.id}-depth.bin`);

    const nodeRes = await fetch(`${API_BASE}/api/property/${id}/node`, { method: 'POST', body: form });
    if (!nodeRes.ok) throw new Error(await nodeRes.text());
  }

  onProgress('物件情報を保存中...', 95);
  const finalRes = await fetch(`${API_BASE}/api/property/${id}/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pinPositions, displacement }),
  });
  if (!finalRes.ok) throw new Error(await finalRes.text());

  onProgress('完了！', 100);
  return id;
}

// ── Update ────────────────────────────────────────────────────────────────────

export async function updateProperty(
  propertyId: string,
  name: string,
  address: string,
  nodes: SpaceNode[],
  existingNodeMeta: Record<string, NodeMeta>,
  deletedNodeIds: string[],
  pinPositions: Record<string, [number, number, number]>,
  displacement: number,
  onProgress: (msg: string, pct: number) => void,
): Promise<void> {
  onProgress('更新を開始中...', 2);
  const initRes = await fetch(`${API_BASE}/api/property/${propertyId}/update-init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, address }),
  });
  if (!initRes.ok) throw new Error(await initRes.text());

  const newNodes = nodes.filter(n => n.imageUrl.startsWith('blob:'));

  for (let i = 0; i < newNodes.length; i++) {
    const node = newNodes[i];
    const pct = 5 + Math.round((i / Math.max(newNodes.length, 1)) * 85);
    onProgress(`「${node.name}」をアップロード中...`, pct);

    const imageBlob = await fetch(node.imageUrl).then(r => r.blob());
    const depthArr = node.depthMap!;
    const depthCopy2 = depthArr.buffer.slice(depthArr.byteOffset, depthArr.byteOffset + depthArr.byteLength) as ArrayBuffer;
    const depthBlob = new Blob([depthCopy2], { type: 'application/octet-stream' });

    const form = new FormData();
    form.append('nodeId', node.id);
    form.append('name', node.name);
    form.append('depthWidth', String(node.depthWidth!));
    form.append('depthHeight', String(node.depthHeight!));
    form.append('image', imageBlob, `${node.id}-image.jpg`);
    form.append('depth', depthBlob, `${node.id}-depth.bin`);

    const nodeRes = await fetch(`${API_BASE}/api/property/${propertyId}/node`, { method: 'POST', body: form });
    if (!nodeRes.ok) throw new Error(await nodeRes.text());
  }

  onProgress('物件情報を保存中...', 95);
  const existingNodes = nodes
    .filter(n => !n.imageUrl.startsWith('blob:'))
    .map(n => ({ id: n.id, nodeName: n.name, ...existingNodeMeta[n.id] }));

  const newNodeIds = newNodes.map(n => n.id);

  const updateRes = await fetch(`${API_BASE}/api/property/${propertyId}/update-meta`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, address, pinPositions, displacement, existingNodes, newNodeIds, deletedNodeIds }),
  });
  if (!updateRes.ok) throw new Error(await updateRes.text());

  onProgress('完了！', 100);
}

// ── Delete ────────────────────────────────────────────────────────────────────

export async function deleteProperty(propertyId: string, _nodeIds: string[]): Promise<void> {
  // meta.json からnode IDを取得（index.jsonには含まれないため）
  const meta = await fetch(`${HTTP_BASE}/${propertyId}/meta.json`)
    .then(r => r.ok ? r.json() : null).catch(() => null);
  const nodeIds: string[] = meta?.nodes?.map((n: { id: string }) => n.id) ?? _nodeIds;

  await fetch(`${API_BASE}/api/property/${propertyId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nodeIds }),
  });
}
