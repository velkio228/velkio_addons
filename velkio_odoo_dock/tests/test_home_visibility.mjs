// Run with: node velkio_odoo_dock/tests/test_home_visibility.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

let source = fs.readFileSync(new URL('../static/src/dock/velkio_dock.js', import.meta.url), 'utf8');
source = source.replace(/import\s+[\s\S]*?from\s+["'][^"']+["'];/g, '').replace(/export /g, '');
const properties = new Map();
let timerCleared = false;
const context = {
    Component: class {}, Dialog: class {}, _t: (s) => s,
    user: { name: 'Test User', activeCompany: { id: 7, name: 'Test Company' } },
    registry: { category: () => ({ add() {} }) },
    browser: { clearTimeout: () => { timerCleared = true; } },
    document: { body: { classList: { add() {}, remove() {} },
        style: { setProperty: (name, value) => properties.set(name, value) } } },
};
vm.createContext(context);
vm.runInContext(source + '\nthis.Dock = VelkioDock;', context);
const dock = Object.create(context.Dock.prototype);
dock.env = { services: { home_menu: { hasHomeMenu: true } } };
dock.state = {
    settings: { position: 'left', style: 'floating', icon_size: 'medium', autohide: false },
    tooltip: {}, contextMenu: {}, overviewOpen: true, revealed: true,
};
const originalSettings = JSON.stringify(dock.state.settings);
dock.syncHomeVisibility();
dock.applyBodyLayout();
assert.equal(dock.state.homeVisible, true);
assert.ok(parseFloat(properties.get('--o-velkio-dock-space')) > 0);
assert.equal(dock.state.tooltip, null);
assert.equal(dock.state.contextMenu, null);
assert.equal(dock.state.overviewOpen, false);
assert.equal(timerCleared, true);

dock.env.services.home_menu.hasHomeMenu = false;
dock.syncHomeVisibility();
dock.applyBodyLayout();
assert.equal(dock.state.homeVisible, false);
assert.ok(parseFloat(properties.get('--o-velkio-dock-space')) > 0);
assert.equal(JSON.stringify(dock.state.settings), originalSettings);

delete dock.env.services.home_menu;
dock.syncHomeVisibility();
assert.equal(dock.state.homeVisible, false);
dock.state.settings.autohide = true;
dock.env.services.home_menu = { hasHomeMenu: true };
dock.syncHomeVisibility();
dock.applyBodyLayout();
assert.ok(parseFloat(properties.get('--o-velkio-dock-space')) > 0);
assert.ok(!dock.dockClass.includes('o_velkio_dock_autohide'));
dock.env.services.home_menu.hasHomeMenu = false;
dock.syncHomeVisibility();
dock.applyBodyLayout();
assert.equal(properties.get('--o-velkio-dock-space'), '0px');
for (const [hour, expected] of [[4, 'Good night'], [5, 'Good morning'], [12, 'Good afternoon'], [17, 'Good evening'], [21, 'Good night']]) {
    dock.state.workspaceNow = new Date(2026, 9, 7, hour).getTime();
    assert.equal(dock.workspaceGreeting, `${expected}, Test User`);
}
assert.equal(dock.workspaceCompanyLogo, '/web/image/res.company/7/logo');
const before = dock.workspaceTime;
dock.state.workspaceNow += 1000;
assert.notEqual(dock.workspaceTime, before);
console.log('Home visibility regressions passed: dock stays visible on home; overlays cleared; auto-hide resumes in apps; Community preserved.');
