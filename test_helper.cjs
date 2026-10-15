'use strict';
// Exercise routing with fake account-file existence; no credentials or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, 'wb_credits_helper.cjs'), 'utf8');
const prefix = source.slice(0, source.indexOf('function loadKey()'));
function route(platform, execPath, variant = 'auto') {
  const context = {require: name => name === 'fs' ? {existsSync: () => true} : require(name),
    process: {platform, execPath, env: {}, argv: []}};
  vm.createContext(context);
  return vm.runInContext(prefix + '\nresolveVariant(' + JSON.stringify(variant) + ')', context);
}
assert.equal(route('win32', 'E:\\Programs\\WorkBuddyAI\\WorkBuddyAI.exe'), 'ai');
assert.equal(route('win32', 'D:\\Programs\\WorkBuddy\\WorkBuddy.exe'), 'cn');
assert.equal(route('win32', 'E:/WorkBuddyAI/WORKBUDDYAI.EXE'), 'ai');
assert.equal(route('darwin', '/Applications/WorkBuddy AI.app/Contents/MacOS/Electron'), 'ai');
assert.equal(route('darwin', '/Applications/WorkBuddy.app/Contents/MacOS/Electron'), 'cn');
assert.equal(route('win32', 'E:/WorkBuddyAI/WorkBuddyAI.exe', 'cn'), 'cn');
assert.equal(route('win32', 'C:/node.exe', 'ai'), 'ai');
console.log('7 helper routing assertions passed (no accounts or network).');
