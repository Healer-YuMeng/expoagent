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

const {
  AUTH_SESSION_DURATION_MS,
  isSessionExpired,
  parseSessionTimestamp,
  resolvePostLoginPath,
} = loadTsModule('src/utils/authSession.ts');

test('12小时内会话保持有效', () => {
  const loginAt = 1_700_000_000_000;

  assert.equal(isSessionExpired(loginAt, loginAt + AUTH_SESSION_DURATION_MS - 1), false);
});

test('超过12小时会话失效', () => {
  const loginAt = 1_700_000_000_000;

  assert.equal(isSessionExpired(loginAt, loginAt + AUTH_SESSION_DURATION_MS), true);
});

test('登录后优先返回原始受保护页面', () => {
  assert.equal(
    resolvePostLoginPath('/admin-system', '/expo-system'),
    '/admin-system',
  );
  assert.equal(
    resolvePostLoginPath('/expo-system/dashboard/leads/123', '/expo-system'),
    '/expo-system/dashboard/leads/123',
  );
});

test('非法回跳地址回退到角色首页', () => {
  assert.equal(resolvePostLoginPath('https://evil.example.com', '/expo-system'), '/expo-system');
  assert.equal(resolvePostLoginPath('/auth/login', '/expo-system'), '/expo-system');
  assert.equal(resolvePostLoginPath('', '/expo-system'), '/expo-system');
});

test('会话时间戳解析异常时返回空值', () => {
  assert.equal(parseSessionTimestamp('abc'), null);
  assert.equal(parseSessionTimestamp(null), null);
});
