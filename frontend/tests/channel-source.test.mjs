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
    URL,
    URLSearchParams,
    require(specifier) {
      throw new Error(`Unsupported import in test loader: ${specifier}`);
    },
  };

  vm.runInNewContext(transpiled.outputText, context, { filename: filePath });
  return module.exports;
}

const {
  buildChannelUrl,
  buildStartChatEntryUrl,
} = loadTsModule('src/utils/channelSource.ts');

test('渠道二维码默认落到 start-chat 而不是首页', () => {
  assert.equal(
    buildChannelUrl('http://localhost:8606/', 'xhs'),
    'http://localhost:8606/start-chat?source=xhs',
  );
});

test('固定聊天入口可以保留已有参数并补充来源参数', () => {
  assert.equal(
    buildStartChatEntryUrl('http://localhost:8606/start-chat?assistant_id=abc', { source: 'dy' }),
    'http://localhost:8606/start-chat?assistant_id=abc&source=dy',
  );
});

