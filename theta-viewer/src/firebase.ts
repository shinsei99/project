import { createClient } from '@supabase/supabase-js';
import type { SpaceNode } from './types';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const isConfigured = !!(supabaseUrl && supabaseKey);

const supabase = isConfigured ? createClient(supabaseUrl, supabaseKey) : null;

const BUCKET = 'theta-space';

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
  depthPath: string;
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

// ── Save ──────────────────────────────────────────────────────────────────────

export async function saveProperty(
  name: string,
  address: string,
  nodes: SpaceNode[],
  pinPositions: Record<string, [number, number, number]>,
  displacement: number,
  onProgress: (msg: string, pct: number) => void,
): Promise<string> {
  if (!supabase) throw new Error('Supabase が設定されていません');

  const propertyId = crypto.randomUUID().slice(0, 12);
  const nodeData: Record<string, object> = {};

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const base = Math.round((i / nodes.length) * 85);

    onProgress(`「${node.name}」の画像をアップロード中...`, base);
    const imageBlob = await fetch(node.imageUrl).then(r => r.blob());
    const imagePath = `properties/${propertyId}/${node.id}/image.jpg`;
    const { error: imgErr } = await supabase.storage
      .from(BUCKET).upload(imagePath, imageBlob, { contentType: 'image/jpeg' });
    if (imgErr) throw imgErr;
    const imageUrl = supabase.storage.from(BUCKET).getPublicUrl(imagePath).data.publicUrl;

    onProgress(`「${node.name}」の深度データをアップロード中...`, base + 10);
    const arr = node.depthMap!;
    const depthBuffer = arr.buffer.slice(arr.byteOffset, arr.byteOffset + arr.byteLength);
    const depthPath = `properties/${propertyId}/${node.id}/depth.bin`;
    const { error: depthErr } = await supabase.storage
      .from(BUCKET).upload(depthPath, new Uint8Array(depthBuffer), { contentType: 'application/octet-stream' });
    if (depthErr) throw depthErr;

    nodeData[node.id] = {
      name: node.name, imageUrl, depthPath,
      depthWidth: node.depthWidth!, depthHeight: node.depthHeight!,
    };
  }

  onProgress('物件情報を保存中...', 95);

  const { error } = await supabase.from('properties').insert({
    id: propertyId,
    name,
    address,
    node_order: nodes.map(n => n.id),
    node_data: nodeData,
    pin_positions: pinPositions,
    displacement,
  });
  if (error) throw error;

  onProgress('完了！', 100);
  return propertyId;
}

// ── Load ──────────────────────────────────────────────────────────────────────

export async function loadProperty(propertyId: string): Promise<PropertyViewData> {
  if (!supabase) throw new Error('Supabase が設定されていません');

  const { data, error } = await supabase
    .from('properties').select('*').eq('id', propertyId).single();
  if (error) throw error;
  if (!data) throw new Error('物件が見つかりません (ID: ' + propertyId + ')');

  const nodeData = data.node_data as Record<string, NodeMeta>;

  const nodes: SpaceNode[] = [];
  for (const nodeId of data.node_order as string[]) {
    const nd = nodeData[nodeId];

    const { data: depthBlob, error: depthErr } = await supabase.storage
      .from(BUCKET).download(nd.depthPath);
    if (depthErr) throw depthErr;

    nodes.push({
      id: nodeId,
      name: nd.name,
      imageUrl: nd.imageUrl,
      status: 'done',
      progress: 100,
      message: '',
      depthMap: new Float32Array(await depthBlob!.arrayBuffer()),
      depthWidth: nd.depthWidth,
      depthHeight: nd.depthHeight,
    });
  }

  return {
    id: propertyId,
    name: data.name as string,
    address: (data.address as string) ?? '',
    nodes,
    pinPositions: (data.pin_positions as Record<string, [number, number, number]>) ?? {},
    displacement: (data.displacement as number) ?? 1.5,
    rawNodeData: nodeData,
  };
}

// ── Update ─────────────────────────────────────────────────────────────────────

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
  if (!supabase) throw new Error('Supabase が設定されていません');

  // Delete removed nodes from Storage
  if (deletedNodeIds.length > 0) {
    const paths = deletedNodeIds.flatMap(nid => [
      `properties/${propertyId}/${nid}/image.jpg`,
      `properties/${propertyId}/${nid}/depth.bin`,
    ]);
    await supabase.storage.from(BUCKET).remove(paths);
  }

  const newNodeData: Record<string, object> = {};
  const newNodes = nodes.filter(n => n.imageUrl.startsWith('blob:'));
  const existingNodes = nodes.filter(n => !n.imageUrl.startsWith('blob:'));

  // Keep existing nodes (update name only)
  for (const node of existingNodes) {
    const meta = existingNodeMeta[node.id];
    newNodeData[node.id] = { ...meta, name: node.name };
  }

  // Upload new nodes
  for (let i = 0; i < newNodes.length; i++) {
    const node = newNodes[i];
    const pct = Math.round((i / newNodes.length) * 85);
    onProgress(`「${node.name}」の画像をアップロード中...`, pct);

    const imageBlob = await fetch(node.imageUrl).then(r => r.blob());
    const imagePath = `properties/${propertyId}/${node.id}/image.jpg`;
    const { error: imgErr } = await supabase.storage
      .from(BUCKET).upload(imagePath, imageBlob, { contentType: 'image/jpeg' });
    if (imgErr) throw imgErr;
    const imageUrl = supabase.storage.from(BUCKET).getPublicUrl(imagePath).data.publicUrl;

    onProgress(`「${node.name}」の深度データをアップロード中...`, pct + 10);
    const arr = node.depthMap!;
    const depthBuffer = arr.buffer.slice(arr.byteOffset, arr.byteOffset + arr.byteLength);
    const depthPath = `properties/${propertyId}/${node.id}/depth.bin`;
    const { error: depthErr } = await supabase.storage
      .from(BUCKET).upload(depthPath, new Uint8Array(depthBuffer), { contentType: 'application/octet-stream' });
    if (depthErr) throw depthErr;

    newNodeData[node.id] = {
      name: node.name, imageUrl, depthPath,
      depthWidth: node.depthWidth!, depthHeight: node.depthHeight!,
    };
  }

  onProgress('物件情報を保存中...', 95);

  const { error } = await supabase.from('properties').update({
    name,
    address,
    node_order: nodes.map(n => n.id),
    node_data: newNodeData,
    pin_positions: pinPositions,
    displacement,
  }).eq('id', propertyId);
  if (error) throw error;

  onProgress('完了！', 100);
}

// ── List ──────────────────────────────────────────────────────────────────────

export async function listProperties(): Promise<PropertySummary[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from('properties').select('id, name, address, created_at, node_order').order('created_at', { ascending: false });
  if (error) throw error;
  return (data ?? []).map(r => ({
    id: r.id as string,
    name: (r.name as string) ?? '（名称未設定）',
    address: (r.address as string) ?? '',
    createdAt: new Date(r.created_at as string),
    roomCount: (r.node_order as string[]).length,
    nodeOrder: r.node_order as string[],
  }));
}

// ── Delete ────────────────────────────────────────────────────────────────────

export async function deleteProperty(propertyId: string, nodeIds: string[]): Promise<void> {
  if (!supabase) return;
  const paths = nodeIds.flatMap(nid => [
    `properties/${propertyId}/${nid}/image.jpg`,
    `properties/${propertyId}/${nid}/depth.bin`,
  ]);
  await supabase.storage.from(BUCKET).remove(paths);
  await supabase.from('properties').delete().eq('id', propertyId);
}
