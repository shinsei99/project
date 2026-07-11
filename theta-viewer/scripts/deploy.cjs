#!/usr/bin/env node
// dist/ の中身を daikyocorp.co.jp/www/htdocs/vr/ にデプロイ
// 物件データ（{id}/ サブディレクトリ）は上書きしない

const ftp = require('/Users/apple/theta-viewer/server/node_modules/basic-ftp');
const fs = require('fs');
const path = require('path');

const FTP_HOST = 'daikyocorp.co.jp';
const FTP_USER = 'mw2pqwm3xa';
const FTP_PASS = 'MgpCRN73#';
const FTP_ROOT = '/www/htdocs/vr';
const DIST = path.join(__dirname, '../dist');

async function uploadDir(client, localDir, remoteDir) {
  const entries = fs.readdirSync(localDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === '.git') continue;
    const localPath = path.join(localDir, entry.name);
    const remotePath = `${remoteDir}/${entry.name}`;
    if (entry.isDirectory()) {
      await uploadDir(client, localPath, remotePath);
    } else {
      await client.ensureDir(remoteDir); // カレントディレクトリを毎回セット
      process.stdout.write(`  → ${remotePath}\n`);
      await client.uploadFrom(localPath, entry.name);
    }
  }
}

(async () => {
  const client = new ftp.Client(0);
  client.ftp.verbose = false;
  try {
    await client.access({ host: FTP_HOST, user: FTP_USER, password: FTP_PASS, secure: false });
    console.log('FTP接続OK');
    await uploadDir(client, DIST, FTP_ROOT);
    console.log('\nデプロイ完了 → https://daikyocorp.co.jp/vr/');
  } catch (e) {
    console.error('デプロイ失敗:', e);
    process.exit(1);
  } finally {
    client.close();
  }
})();
