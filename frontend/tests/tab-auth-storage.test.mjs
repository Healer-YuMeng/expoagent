import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from '../node_modules/typescript/lib/typescript.js';

function loadTsModule(relativePath) {
  const filePath = path.resolve(process.cwd(), relativePath);
  const source = fs.readFileSync(filePath, 'utf8');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  });

  const module = { exports: {} };
  const context = {
    module,
    exports: module.exports,
    require(specifier) {
      throw new Error(`Unsupported import in test loader: ${specifier}`);
    },
  };

  vm.runInNewContext(transpiled.outputText, context, { filename: filePath });
  return module.exports;
}

function createStorage(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

const {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  AUTH_LOGIN_AT_KEY,
  clearAdminAuthStorage,
  loadAdminAuthStorage,
  persistAdminAuthStorage,
} = loadTsModule('src/utils/adminAuthStorage.ts');

test('优先使用当前标签页的后台登录态', () => {
  const session = createStorage({
    [AUTH_TOKEN_KEY]: 'teacher-token',
    [AUTH_USER_KEY]: '{"role":"teacher"}',
    [AUTH_LOGIN_AT_KEY]: '1700000000000',
  });
  const local = createStorage({
    [AUTH_TOKEN_KEY]: 'root-token',
    [AUTH_USER_KEY]: '{"role":"super_admin"}',
    [AUTH_LOGIN_AT_KEY]: '1700000009999',
  });

  const snapshot = loadAdminAuthStorage(session, local);

  assert.equal(snapshot.token, 'teacher-token');
  assert.equal(snapshot.userJson, '{"role":"teacher"}');
  assert.equal(snapshot.loginAt, '1700000000000');
});

test('当前标签页为空时迁移旧的共享登录态到当前标签页', () => {
  const session = createStorage();
  const local = createStorage({
    [AUTH_TOKEN_KEY]: 'legacy-token',
    [AUTH_USER_KEY]: '{"role":"school_admin"}',
    [AUTH_LOGIN_AT_KEY]: '1700000001111',
  });

  const snapshot = loadAdminAuthStorage(session, local);

  assert.equal(snapshot.token, 'legacy-token');
  assert.equal(session.getItem(AUTH_TOKEN_KEY), 'legacy-token');
  assert.equal(local.getItem(AUTH_TOKEN_KEY), null);
});

test('后台登录态只写入当前标签页存储', () => {
  const session = createStorage();
  const local = createStorage();

  persistAdminAuthStorage(session, local, 'new-token', '{"role":"teacher"}', 1700000002222);

  assert.equal(session.getItem(AUTH_TOKEN_KEY), 'new-token');
  assert.equal(local.getItem(AUTH_TOKEN_KEY), null);
});

test('清理后台登录态时同时删除当前页和旧共享存储', () => {
  const session = createStorage({
    [AUTH_TOKEN_KEY]: 'teacher-token',
    [AUTH_USER_KEY]: '{"role":"teacher"}',
    [AUTH_LOGIN_AT_KEY]: '1700000000000',
  });
  const local = createStorage({
    [AUTH_TOKEN_KEY]: 'legacy-token',
    [AUTH_USER_KEY]: '{"role":"super_admin"}',
    [AUTH_LOGIN_AT_KEY]: '1700000009999',
  });

  clearAdminAuthStorage(session, local);

  assert.equal(session.getItem(AUTH_TOKEN_KEY), null);
  assert.equal(local.getItem(AUTH_TOKEN_KEY), null);
});
