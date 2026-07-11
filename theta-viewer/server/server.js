const express = require('express');
const cors = require('cors');
const multer = require('multer');
const ftp = require('basic-ftp');
const { Writable, PassThrough } = require('stream');
const path = require('path');

const FTP_HOST = 'daikyocorp.co.jp';
const FTP_USER = 'mw2pqwm3xa';
const FTP_PASS = 'MgpCRN73#';
const FTP_ROOT = '/www/htdocs/vr';
const HTTP_BASE = 'https://daikyocorp.co.jp/vr';
const PORT = 8519;
const SESSION_TTL = 60 * 60 * 1000; // 1時間（15部屋対応）

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024 }, // 100MB
});

// セッション: メタデータのみ保持（FTP接続はAPI呼び出しごとに新規作成）
const sessions = new Map(); // id → { nodes, name, address, timer }

// ── FTP ヘルパー ───────────────────────────────────────────────────────────────

function bufferToStream(buffer) {
  const pt = new PassThrough();
  pt.end(buffer);
  return pt;
}

// FTP接続を新規作成してfnを実行し、必ずcloseする（タイムアウト0=制限なし）
async function withFtp(fn) {
  const client = new ftp.Client(0); // 0=タイムアウトなし
  client.ftp.verbose = false;
  try {
    await client.access({ host: FTP_HOST, user: FTP_USER, password: FTP_PASS, secure: false });
    return await fn(client);
  } finally {
    try { client.close(); } catch {}
  }
}

async function ftpUpload(client, remotePath, buffer) {
  const dir = path.posix.dirname(remotePath);
  const filename = path.posix.basename(remotePath);
  await client.ensureDir(dir);
  await client.uploadFrom(bufferToStream(buffer), filename);
}

async function ftpReadJson(client, remotePath) {
  const chunks = [];
  const ws = new Writable({ write(chunk, _, cb) { chunks.push(chunk); cb(); } });
  try {
    await client.ensureDir(path.posix.dirname(remotePath));
    await client.downloadTo(ws, path.posix.basename(remotePath));
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    return null;
  }
}

async function ftpDeleteFile(client, remotePath) {
  try {
    await client.cd(path.posix.dirname(remotePath));
    await client.remove(path.posix.basename(remotePath));
  } catch {}
}

function cleanupSession(id) {
  const s = sessions.get(id);
  if (s) { clearTimeout(s.timer); sessions.delete(id); }
}

// ── 新規物件 ───────────────────────────────────────────────────────────────────

app.post('/api/property/init', async (req, res) => {
  try {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    const { name, address } = req.body;
    const timer = setTimeout(() => cleanupSession(id), SESSION_TTL);
    sessions.set(id, { nodes: [], name, address, timer });
    res.json({ id });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

app.post('/api/property/:id/node',
  upload.fields([{ name: 'image', maxCount: 1 }, { name: 'depth', maxCount: 1 }]),
  async (req, res) => {
    try {
      const { id } = req.params;
      const session = sessions.get(id);
      if (!session) return res.status(404).json({ error: 'セッションが見つかりません。やり直してください。' });

      const { nodeId, name, depthWidth, depthHeight } = req.body;
      const imageBuffer = req.files['image'][0].buffer;
      const depthBuffer = req.files['depth'][0].buffer;

      // ノードごとに新規FTP接続（タイムアウト回避）
      await withFtp(async (client) => {
        await ftpUpload(client, `${FTP_ROOT}/${id}/${nodeId}-image.jpg`, imageBuffer);
        await ftpUpload(client, `${FTP_ROOT}/${id}/${nodeId}-depth.bin`, depthBuffer);
      });

      session.nodes.push({
        id: nodeId, name,
        imageUrl: `${HTTP_BASE}/${id}/${nodeId}-image.jpg`,
        depthUrl: `${HTTP_BASE}/${id}/${nodeId}-depth.bin`,
        depthWidth: Number(depthWidth),
        depthHeight: Number(depthHeight),
      });

      res.json({ ok: true });
    } catch (e) {
      console.error(e);
      res.status(500).json({ error: String(e) });
    }
  }
);

app.post('/api/property/:id/finalize', async (req, res) => {
  const { id } = req.params;
  const session = sessions.get(id);
  if (!session) return res.status(404).json({ error: 'セッションが見つかりません。' });

  try {
    const { pinPositions, displacement } = req.body;
    const { nodes, name, address } = session;

    const meta = { id, name, address, createdAt: new Date().toISOString(), displacement, pinPositions, nodes };

    await withFtp(async (client) => {
      await ftpUpload(client, `${FTP_ROOT}/${id}/meta.json`, Buffer.from(JSON.stringify(meta)));
      const index = (await ftpReadJson(client, `${FTP_ROOT}/index.json`)) || [];
      index.unshift({ id, name, address, createdAt: meta.createdAt, roomCount: nodes.length });
      await ftpUpload(client, `${FTP_ROOT}/index.json`, Buffer.from(JSON.stringify(index)));
    });

    res.json({ id, url: `${HTTP_BASE}/${id}/meta.json` });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  } finally {
    cleanupSession(id);
  }
});

// ── 既存物件の更新 ─────────────────────────────────────────────────────────────

app.post('/api/property/:id/update-init', async (req, res) => {
  try {
    const { id } = req.params;
    const { name, address } = req.body;
    const timer = setTimeout(() => cleanupSession(id), SESSION_TTL);
    sessions.set(id, { nodes: [], name, address, timer });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

app.post('/api/property/:id/update-node',
  upload.fields([{ name: 'image', maxCount: 1 }, { name: 'depth', maxCount: 1 }]),
  async (req, res) => {
    try {
      const { id } = req.params;
      const session = sessions.get(id);
      if (!session) return res.status(404).json({ error: 'セッションが見つかりません。' });

      const { nodeId, name, depthWidth, depthHeight } = req.body;
      const imageBuffer = req.files['image'][0].buffer;
      const depthBuffer = req.files['depth'][0].buffer;

      await withFtp(async (client) => {
        await ftpUpload(client, `${FTP_ROOT}/${id}/${nodeId}-image.jpg`, imageBuffer);
        await ftpUpload(client, `${FTP_ROOT}/${id}/${nodeId}-depth.bin`, depthBuffer);
      });

      session.nodes.push({
        id: nodeId, name,
        imageUrl: `${HTTP_BASE}/${id}/${nodeId}-image.jpg`,
        depthUrl: `${HTTP_BASE}/${id}/${nodeId}-depth.bin`,
        depthWidth: Number(depthWidth),
        depthHeight: Number(depthHeight),
      });

      res.json({ ok: true });
    } catch (e) {
      console.error(e);
      res.status(500).json({ error: String(e) });
    }
  }
);

app.post('/api/property/:id/update-meta', async (req, res) => {
  const { id } = req.params;
  const session = sessions.get(id);
  if (!session) return res.status(404).json({ error: 'セッションが見つかりません。' });

  try {
    const { name, address, pinPositions, displacement, existingNodes, newNodeIds, deletedNodeIds } = req.body;
    const newNodes = session.nodes.filter(n => (newNodeIds || []).includes(n.id));
    const allNodes = [...(existingNodes || []), ...newNodes];
    const meta = { id, name, address, createdAt: new Date().toISOString(), displacement, pinPositions, nodes: allNodes };

    await withFtp(async (client) => {
      for (const nodeId of (deletedNodeIds || [])) {
        await ftpDeleteFile(client, `${FTP_ROOT}/${id}/${nodeId}-image.jpg`);
        await ftpDeleteFile(client, `${FTP_ROOT}/${id}/${nodeId}-depth.bin`);
      }
      await ftpUpload(client, `${FTP_ROOT}/${id}/meta.json`, Buffer.from(JSON.stringify(meta)));
      const index = (await ftpReadJson(client, `${FTP_ROOT}/index.json`)) || [];
      const idx = index.findIndex(p => p.id === id);
      const entry = { id, name, address, createdAt: meta.createdAt, roomCount: allNodes.length };
      if (idx >= 0) index[idx] = entry; else index.unshift(entry);
      await ftpUpload(client, `${FTP_ROOT}/index.json`, Buffer.from(JSON.stringify(index)));
    });

    res.json({ ok: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  } finally {
    cleanupSession(id);
  }
});

// ── 物件削除 ───────────────────────────────────────────────────────────────────

app.delete('/api/property/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { nodeIds } = req.body;

    await withFtp(async (client) => {
      for (const nodeId of (nodeIds || [])) {
        await ftpDeleteFile(client, `${FTP_ROOT}/${id}/${nodeId}-image.jpg`);
        await ftpDeleteFile(client, `${FTP_ROOT}/${id}/${nodeId}-depth.bin`);
      }
      await ftpDeleteFile(client, `${FTP_ROOT}/${id}/meta.json`);
      try { await client.removeDir(`${FTP_ROOT}/${id}`); } catch {}
      const index = (await ftpReadJson(client, `${FTP_ROOT}/index.json`)) || [];
      await ftpUpload(client, `${FTP_ROOT}/index.json`,
        Buffer.from(JSON.stringify(index.filter(p => p.id !== id))));
    });

    res.json({ ok: true });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`theta-space FTP API listening on :${PORT}`);
});
