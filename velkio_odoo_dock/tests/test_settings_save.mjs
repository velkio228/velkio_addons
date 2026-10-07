// Run with: node velkio_odoo_dock/tests/test_settings_save.mjs
// Exercise the shipped dialog's save and destruction behavior without a server.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

let code = fs.readFileSync(new URL('../static/src/dock/velkio_dock.js', import.meta.url), 'utf8');
code = code.replace(/import\s+[\s\S]*?from\s+["'][^"']+["'];/g, '').replace(/export /g, '');
let destroy;
const context = {
    Component: class {}, Dialog: class {}, _t: (s) => s,
    registry: { category: () => ({ add() {} }) },
    useState: (state) => state,
    onWillDestroy: (callback) => { destroy = callback; },
};
vm.createContext(context);
vm.runInContext(code + '\nthis.Settings = VelkioDockSettings;', context);

function dialog(onSave) {
    const preview = [];
    let closed = false;
    const instance = Object.create(context.Settings.prototype);
    instance.props = {
        settings: { position: 'left' }, onSave,
        onPreview: (settings) => preview.push(settings.position),
        close: () => { closed = true; destroy(); },
    };
    instance.setup();
    return { instance, preview, isClosed: () => closed };
}

const failed = dialog(async () => { throw new Error('Network unavailable'); });
failed.instance.set('position', 'right');
await assert.rejects(() => failed.instance.save(), /Network unavailable/);
assert.equal(failed.isClosed(), false);
assert.equal(failed.instance.saved, false);
destroy();
assert.deepEqual(failed.preview, ['right', 'left']);

const successful = dialog(async () => {});
successful.instance.set('position', 'bottom');
await successful.instance.save();
assert.equal(successful.isClosed(), true);
assert.equal(successful.instance.saved, true);
assert.deepEqual(successful.preview, ['bottom']);
console.log('Settings save regressions: failure rolls back on close; success keeps changes.');
