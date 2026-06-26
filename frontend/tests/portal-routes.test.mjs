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
  getControlledPortalFeatureTarget,
  getPortalHomePath,
  getPortalPath,
  getParentConversationPath,
  isPortalFeatureLocked,
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

test('功能开关只控制四个指定模块', () => {
  const disabledModules = {
    manualCallbacks: false,
    systemPrompt: false,
    userManagement: false,
    systemSettings: false,
  };

  assert.equal(getControlledPortalFeatureTarget('super_admin', '/admin-system/system-settings'), 'systemSettings');
  assert.equal(getControlledPortalFeatureTarget('admin', '/expo-system/manual-callbacks'), 'manualCallbacks');
  assert.equal(getControlledPortalFeatureTarget('sales', '/expo-system/user/leads'), null);

  assert.equal(isPortalFeatureLocked('admin', '/expo-system/manual-callbacks', disabledModules), true);
  assert.equal(isPortalFeatureLocked('sales', '/expo-system/user/system-settings', disabledModules), true);
  assert.equal(isPortalFeatureLocked('super_admin', '/admin-system/system-settings', disabledModules), false);
  assert.equal(isPortalFeatureLocked('admin', '/expo-system/leads', disabledModules), false);
});
