/*
 * WorkBuddy 积分取数助手
 * ------------------------------------------------------------------
 * 由 WorkBuddy 自带的 Electron 运行时以「node 模式」执行，一次完成：
 *   1. 通过官方原生绑定拿到落盘加密用的 atRestSecretKey
 *   2. 用 sha256(atRestSecretKey) 派生密钥，解开 .info 登录态里的 accessToken
 *   3. 用解出的 Bearer Token 调官方计费接口，返回剩余积分
 * 结果以单行 JSON 写到 stdout。
 *
 * 说明：官方客户端自 5.6 起把 accessToken / refreshToken 从明文改成
 * `{"$wbEncrypted":1,"envelope":"base64(...)"}`（AES-256-GCM）信封，
 * 直接读文件拿到的是密文。这里复刻官方 at-rest-crypto 的解密链路。
 *
 * 用法：
 *   set ELECTRON_RUN_AS_NODE=1
 *   "C:\...\WorkBuddy.exe" wb_credits_helper.cjs [--variant cn|ai]
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const https = require('https');

const VARIANTS = {
  cn: {
    authFile: 'workbuddy-desktop.info',
    domain: 'www.workbuddy.cn',
    host: 'www.workbuddy.cn',
  },
  ai: {
    authFile: 'workbuddy-desktop-ai.info',
    domain: 'www.workbuddy.ai',
    host: 'www.workbuddy.ai',
  },
};

// 计费接口路径（国内版与国际版同构）
const SUMMARY_PATH = '/billing/meter/get-user-resource-summary';
const RESOURCE_PATH = '/billing/meter/get-user-resource';

function emit(obj) {
  process.stdout.write(JSON.stringify(obj));
  process.exit(0);
}
function fail(code, message) {
  emit({ ok: false, code, error: String(message || '') });
}

function readVariantArg() {
  const i = process.argv.indexOf('--variant');
  const v = i >= 0 ? process.argv[i + 1] : 'auto';
  return v === 'cn' || v === 'ai' ? v : 'auto';
}

// 自动识别档位：优先国内版，其次国际版
function resolveVariant(variant) {
  if (variant !== 'auto') return variant;
  const base = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
  const root = path.join(base, 'CodeBuddyExtension', 'Data', 'Public', 'auth');
  for (const v of ['cn', 'ai']) {
    if (fs.existsSync(path.join(root, VARIANTS[v].authFile))) return v;
  }
  return 'cn';
}

// ---------------------------------------------------------------- 1. 密钥
function loadKey() {
  let raw;
  try {
    raw = process._linkedBinding('electron_browser_workbuddy_storage').loggerGet();
  } catch (e) {
    throw Object.assign(new Error('无法读取 WorkBuddy 加密密钥（原生绑定不可用）'), { code: 'binding' });
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    throw Object.assign(new Error('加密密钥载荷解析失败'), { code: 'binding' });
  }
  const secret = payload && payload.atRestSecretKey;
  if (typeof secret !== 'string' || secret.length === 0) {
    throw Object.assign(new Error('加密密钥缺失（客户端版本可能不支持）'), { code: 'binding' });
  }
  const keyBytes = Buffer.from(secret, 'base64');
  if (keyBytes.length !== 32) {
    throw Object.assign(new Error('加密密钥长度异常'), { code: 'binding' });
  }
  // key = sha256(base64 文本本身)，与官方 at-rest-crypto 一致
  const key = crypto.createHash('sha256').update(secret, 'utf8').digest();
  keyBytes.fill(0);
  return key;
}

// 由密钥派生 keyId：sha256(key) 的前 16 个 hex
function keyIdOf(key) {
  return crypto.createHash('sha256').update(key).digest('hex').slice(0, 16);
}

// ---------------------------------------------------------- 2. AES-GCM 解密
function lp(text) {
  const b = Buffer.from(String(text), 'utf8');
  const len = Buffer.alloc(4);
  len.writeUInt32BE(b.length, 0);
  return Buffer.concat([len, b]);
}
// 字段帧（WBEV1 / code 2）的 AAD，逐字节对齐官方实现
function aadFor(keyId) {
  return Buffer.concat([
    Buffer.from('WB-AAD\0', 'binary'),
    Buffer.from([0x01]),
    lp('WBEV1'),
    lp('sym-v1'),
    Buffer.from([0, 0, 0, 1]), // suite = 1
    lp(keyId),
    Buffer.from([2, 0, 0]), // framing=field, 无序号/收尾
  ]);
}
function looksEncrypted(v) {
  return v && typeof v === 'object' && typeof v.envelope === 'string' && '$wbEncrypted' in v;
}
function decryptField(key, keyId, wrap) {
  if (typeof wrap === 'string') return wrap; // 明文（老版本）
  if (!looksEncrypted(wrap)) return '';
  const env = JSON.parse(Buffer.from(wrap.envelope, 'base64').toString('utf8'));
  if (env.keyId && env.keyId !== keyId) {
    throw Object.assign(new Error('登录态与当前密钥不匹配（尝试重新登录 WorkBuddy）'), { code: 'key-mismatch' });
  }
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm',
    key,
    Buffer.from(env.nonce, 'base64')
  );
  decipher.setAAD(aadFor(env.keyId || keyId));
  decipher.setAuthTag(Buffer.from(env.authTag, 'base64'));
  return Buffer.concat([
    decipher.update(Buffer.from(env.ciphertext, 'base64')),
    decipher.final(),
  ]).toString('utf8');
}

// --------------------------------------------------------------- 3. 读登录态
function authFilePath(variant) {
  const base = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
  return path.join(base, 'CodeBuddyExtension', 'Data', 'Public', 'auth', VARIANTS[variant].authFile);
}

function loadSession(variant) {
  const p = authFilePath(variant);
  if (!fs.existsSync(p)) {
    throw Object.assign(new Error('未找到 WorkBuddy 登录态，请先登录一次 WorkBuddy 客户端'), { code: 'no-auth' });
  }
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    throw Object.assign(new Error('登录态文件解析失败'), { code: 'no-auth' });
  }
  const key = loadKey();
  try {
    const keyId = keyIdOf(key);
    const accessToken = decryptField(key, keyId, doc.auth && doc.auth.accessToken);
    if (!accessToken) {
      throw Object.assign(new Error('登录态缺少 accessToken'), { code: 'no-auth' });
    }
    return {
      accessToken,
      uid: (doc.account && doc.account.uid) || '',
      domain: (doc.auth && doc.auth.domain) || VARIANTS[variant].domain,
    };
  } finally {
    key.fill(0);
  }
}

// ------------------------------------------------------------------ 4. 请求
function post(host, urlPath, headers, bodyObj) {
  return new Promise((resolve, reject) => {
    const body = Buffer.from(JSON.stringify(bodyObj || {}), 'utf8');
    const req = https.request(
      {
        host,
        path: urlPath,
        method: 'POST',
        headers: Object.assign(
          {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            'Accept-Language': 'zh',
            'Content-Length': body.length,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
          },
          headers
        ),
      },
      (res) => {
        let buf = '';
        res.setEncoding('utf8');
        res.on('data', (c) => (buf += c));
        res.on('end', () => resolve({ status: res.statusCode, body: buf }));
      }
    );
    req.on('error', reject);
    req.setTimeout(20000, () => {
      req.destroy(new Error('请求超时'));
    });
    req.write(body);
    req.end();
  });
}

function num(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

// 汇总 summary 响应里的资源包
function summarize(payload) {
  const data = payload && payload.data;
  const packages = Array.isArray(data && data.Packages) ? data.Packages : [];
  const packs = packages.map((p) => ({
    code: p.PackageCode,
    remain: num(p.CycleRemainCapacity),
    total: num(p.CycleTotalCapacity),
    used: num(p.CycleUsedCapacity),
    frozen: num(p.CycleFrozenCapacity),
  }));
  let remain = packs.reduce((s, p) => s + p.remain, 0);
  let total = packs.reduce((s, p) => s + p.total, 0);
  return {
    remain,
    total,
    packages: packs,
    plan: (data && data.SubscriptionPackageName) || '',
    isPaidUser: !!(data && data.IsPaidUser),
    subscriptionCode: (data && data.SubscriptionPackageCode) || '',
  };
}

// ------------------------------------------------------------------- main
(async function main() {
  const variant = resolveVariant(readVariantArg());
  let session;
  try {
    session = loadSession(variant);
  } catch (e) {
    return fail(e.code || 'session', e.message);
  }

  const headers = {
    Authorization: 'Bearer ' + session.accessToken,
    'X-User-Id': session.uid,
  };
  if (session.domain) headers['X-Domain'] = session.domain;

  let summary = null;
  let lastError = null;
  try {
    const r = await post(VARIANTS[variant].host, SUMMARY_PATH, headers, {});
    if (r.status === 200) {
      const j = JSON.parse(r.body);
      if (j && j.code === 0) summary = summarize(j);
      else lastError = `接口返回 code=${j && j.code}`;
    } else if (r.status === 401) {
      return fail('unauthorized', '登录已过期，打开一次 WorkBuddy 客户端即可自动刷新');
    } else {
      lastError = `HTTP ${r.status}`;
    }
  } catch (e) {
    lastError = e.message;
  }

  if (!summary) {
    // 回退到旧接口
    try {
      const r = await post(VARIANTS[variant].host, RESOURCE_PATH, headers, {});
      if (r.status === 200) {
        const j = JSON.parse(r.body);
        const accounts = j && j.data && j.data.Response && j.data.Response.Data && j.data.Response.Data.Accounts;
        if (Array.isArray(accounts)) {
          const packs = accounts.map((a) => ({
            code: a.PackageCode,
            remain: num(a.CycleCapacityRemain),
            total: num(a.CycleCapacitySize),
            used: num(a.CycleCapacityUsed),
            frozen: 0,
          }));
          summary = {
            remain: packs.reduce((s, p) => s + p.remain, 0),
            total: packs.reduce((s, p) => s + p.total, 0),
            packages: packs,
            plan: '',
            isPaidUser: true,
            subscriptionCode: '',
          };
        }
      }
    } catch (_) { /* ignore */ }
  }

  if (!summary) {
    return fail('api', lastError || '接口调用失败');
  }

  const percent = summary.total > 0 ? (summary.remain / summary.total) * 100 : 0;
  emit({
    ok: true,
    variant,
    plan: summary.plan,
    remain: Math.round(summary.remain * 100) / 100,
    total: Math.round(summary.total * 100) / 100,
    percent: Math.round(percent * 10) / 10,
    updatedAt: Date.now(),
  });
})().catch((e) => fail('unknown', (e && e.message) || e));
