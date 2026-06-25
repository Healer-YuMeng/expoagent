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
  getPortalHomePath,
  getPortalPath,
  getParentConversationPath,
  isSchoolAdminFeatureLocked,
} = loadTsModule('src/router/portalRoutes.ts');

test('不同后台角色进入各自独立首页', () => {
  assert.equal(getPortalHomePath('super_admin'), '/admin-system');
  assert.equal(getPortalHomePath('admin'), '/expo-system');
  assert.equal(getPortalHomePath('sales'), '/expo-system/user');
});

test('不同后台角色的功能页前缀不同', () => {
  assert.equal(getPortalPath('super_admin', 'leads'), '/admin-system/leads');
  assert.equal(getPortalPath('admin', 'manualCallbacks'), '/expo-system/manual-callbacks');
  assert.equal(getPortalPath('sales', 'knowledgeBase'), '/expo-system/user/knowledge-base');
});

test('家长对话链接改为 expoagent 前缀', () => {
  assert.equal(
    getParentConversationPath('6a3cdacd26dba624fa9a7cbd'),
    '/expoagent/conversations/6a3cdacd26dba624fa9a7cbd',
  );
});

test('仅学校管理员的指定模块显示开发中蒙版', () => {
  assert.equal(isSchoolAdminFeatureLocked('admin', '/expo-system/manual-callbacks'), true);
  assert.equal(isSchoolAdminFeatureLocked('admin', '/expo-system/system-prompt'), true);
  assert.equal(isSchoolAdminFeatureLocked('admin', '/expo-system/users'), true);
  assert.equal(isSchoolAdminFeatureLocked('admin', '/expo-system/system-settings'), true);
  assert.equal(isSchoolAdminFeatureLocked('admin', '/expo-system/leads'), false);
  assert.equal(isSchoolAdminFeatureLocked('super_admin', '/admin-system/system-settings'), false);
  assert.equal(isSchoolAdminFeatureLocked('sales', '/expo-system/user/system-settings'), false);
});
