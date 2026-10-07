/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillDestroy,
    onWillStart,
    onWillUnmount,
    useEffect,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

const DEFAULT_APP_COUNT = 8;
const RECENT_MAX = 20;
const RECENT_RECORDS_MAX = 15;
const BADGE_REFRESH_MS = 60000;
const OVERVIEW_KEY = "o";
// records opened outside any app (e.g. from a direct URL)
const RECORD_FALLBACK_ICON = {
    iconClass: "fa fa-file-text-o",
    iconStyle: "color: #fff; background-color: #714B67;",
};

export const DOCK_DEFAULTS = {
    position: "left",
    style: "dark",
    icon_size: "medium",
    autohide: false,
    show_recent: true,
    recent_limit: 5,
    accent_color: "#E95420",
    magnify: false,
    shortcuts: true,
    show_badges: true,
    show_favorites: true,
    overview_theme: "auto",
};

const SIZES = {
    small: { icon: 30, item: 40 },
    medium: { icon: 40, item: 52 },
    large: { icon: 52, item: 64 },
};
const DOCK_PADDING = 8; // inner padding on each side of the dock
const FLOAT_GAP = 8; // distance from screen edge for the floating style

export const POSITIONS = [
    { value: "left", label: _t("Left"), icon: "fa-arrow-left" },
    { value: "right", label: _t("Right"), icon: "fa-arrow-right" },
    { value: "top", label: _t("Top"), icon: "fa-arrow-up" },
    { value: "bottom", label: _t("Bottom"), icon: "fa-arrow-down" },
];

export const STYLES = [
    { value: "dark", label: _t("Dark") },
    { value: "floating", label: _t("Floating") },
    { value: "glass", label: _t("Glass") },
    { value: "light", label: _t("Light") },
    { value: "odoo", label: _t("Odoo Purple") },
    { value: "accent", label: _t("Accent Colour") },
];

export const ICON_SIZES = [
    { value: "small", label: _t("Small") },
    { value: "medium", label: _t("Medium") },
    { value: "large", label: _t("Large") },
];

export const OVERVIEW_THEMES = [
    { value: "auto", label: _t("Auto") },
    { value: "dark", label: _t("Dark") },
    { value: "light", label: _t("Light") },
];

export const ACCENT_PRESETS = [
    "#E95420", // orange (default)
    "#714B67", // Odoo purple
    "#017E84", // Odoo teal
    "#2563EB", // blue
    "#16A34A", // green
    "#DC2626", // red
    "#9333EA", // violet
    "#F59E0B", // amber
    "#0F172A", // slate
];

/* ------------------------------------------------------------------ */
/* Icons & links                                                        */
/* ------------------------------------------------------------------ */
function iconInfo(app) {
    const data = app.webIconData || app.web_icon_data;
    if (data && typeof data === "string") {
        // Odoo sends either a data: URI or a plain URL (default icon)
        if (data.startsWith("data:") || data.startsWith("/")) {
            return { iconSrc: data };
        }
        const mime = app.webIconDataMimetype || app.web_icon_data_mimetype || "image/png";
        return { iconSrc: `data:${mime};base64,${data}` };
    }
    const webIcon = app.webIcon || app.web_icon;
    if (webIcon && typeof webIcon === "string") {
        const parts = webIcon.split(",");
        if (parts.length === 2) {
            return { iconSrc: `/${parts[0]}/${parts[1]}` };
        }
        if (parts.length === 3) {
            return {
                iconClass: `fa ${parts[0]}`,
                iconStyle: `color: ${parts[1]}; background-color: ${parts[2]};`,
            };
        }
    }
    return { iconClass: "fa fa-cube", iconStyle: "color:#fff;background-color:#714B67;" };
}

/** Real URL of a menu, so middle-click / Ctrl+click open a new tab. */
function menuHref(menu) {
    if (menu.actionPath) {
        return `/odoo/${menu.actionPath}`;
    }
    if (menu.actionID) {
        return `/odoo/action-${menu.actionID}`;
    }
    return "/odoo";
}

function recordHref(record) {
    return `/odoo/${record.model}/${record.id}`;
}

function toDockApp(app) {
    return { id: app.id, name: app.name, raw: app, href: menuHref(app), ...iconInfo(app) };
}

/** True when the click should be left to the browser (new tab / window). */
function isNewTabClick(ev) {
    return ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button === 1;
}

/* ------------------------------------------------------------------ */
/* Picker dialog: choose which apps are pinned                          */
/* ------------------------------------------------------------------ */
export class VelkioDockPicker extends Component {
    static template = "velkio_odoo_dock.VelkioDockPicker";
    static components = { Dialog };
    static props = {
        apps: Array,
        selectedIds: Array,
        onSave: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ search: "", selected: [...this.props.selectedIds] });
    }

    get filteredApps() {
        const term = this.state.search.trim().toLowerCase();
        return term
            ? this.props.apps.filter((a) => a.name.toLowerCase().includes(term))
            : this.props.apps;
    }

    isSelected(app) {
        return this.state.selected.includes(app.id);
    }

    toggle(app) {
        const idx = this.state.selected.indexOf(app.id);
        if (idx >= 0) {
            this.state.selected.splice(idx, 1);
        } else {
            this.state.selected.push(app.id);
        }
    }

    selectAll() {
        this.state.selected = this.props.apps.map((a) => a.id);
    }

    clearAll() {
        this.state.selected = [];
    }

    async save() {
        await this.props.onSave(this.state.selected);
        this.props.close();
    }
}

/* ------------------------------------------------------------------ */
/* Settings dialog: position, style, size, colour, behaviour            */
/* ------------------------------------------------------------------ */
export class VelkioDockSettings extends Component {
    static template = "velkio_odoo_dock.VelkioDockSettings";
    static components = { Dialog };
    static props = {
        settings: Object,
        onPreview: Function,
        onSave: Function,
        onClearRecent: Function,
        onClearRecentRecords: Function,
        close: Function,
    };

    setup() {
        this.POSITIONS = POSITIONS;
        this.STYLES = STYLES;
        this.ICON_SIZES = ICON_SIZES;
        this.OVERVIEW_THEMES = OVERVIEW_THEMES;
        this.ACCENT_PRESETS = ACCENT_PRESETS;
        this.original = { ...this.props.settings };
        this.saved = false;
        this.ui = useState({ tab: "appearance" });
        this.state = useState({ ...this.props.settings });
        // closing with the X / Esc / Cancel reverts the live preview
        onWillDestroy(() => {
            if (!this.saved) {
                this.props.onPreview(this.original);
            }
        });
    }

    set(key, value) {
        this.state[key] = value;
        this.props.onPreview({ ...this.state });
    }

    onRecentLimit(ev) {
        const value = Math.max(0, Math.min(15, parseInt(ev.target.value, 10) || 0));
        this.set("recent_limit", value);
    }

    reset() {
        Object.assign(this.state, DOCK_DEFAULTS);
        this.props.onPreview({ ...this.state });
    }

    async save() {
        await this.props.onSave({ ...this.state });
        this.saved = true;
        this.props.close();
    }
}

/* ------------------------------------------------------------------ */
/* The dock                                                             */
/* ------------------------------------------------------------------ */
export class VelkioDock extends Component {
    static template = "velkio_odoo_dock.VelkioDock";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.searchRef = useRef("overviewSearch");

        this.state = useState({
            dockIds: [],
            recentIds: [],
            favIds: [],
            recentRecords: [],
            badges: {},
            settings: { ...DOCK_DEFAULTS },
            currentAppId: null,
            dragId: null,
            dragKind: null,
            dropTargetId: null,
            contextMenu: null, // { app, kind: "pinned"|"recent"|"fav", style }
            tooltip: null, // { text, style }
            overviewOpen: false,
            homeVisible: Boolean(this.env.services.home_menu?.hasHomeMenu),
            workspaceNow: Date.now(),
            companyLogoFailed: false,
            overviewSearch: "",
            revealed: false,
        });

        onWillStart(async () => {
            const res = await this.orm.call("velkio.dock.item", "get_dock", []);
            const available = this.allApps.map((a) => a.id);
            const defaults = (res.menu_ids || []).filter((id) => available.includes(id));
            this.state.dockIds =
                res.configured || defaults.length
                    ? defaults
                    : available.slice(0, DEFAULT_APP_COUNT);
            this.state.recentIds = (res.recent_ids || []).filter((id) => available.includes(id));
            this.state.favIds = res.favorite_ids || [];
            this.state.recentRecords = res.recent_records || [];
            this.state.settings = { ...DOCK_DEFAULTS, ...(res.settings || {}) };
            this.updateCurrentApp();
        });

        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            this.updateCurrentApp();
            this.refreshBadges();
        });
        useBus(this.env.bus, "VELKIO_DOCK:RECORD-OPENED", (ev) => this.pushRecentRecord(ev.detail));
        useBus(this.env.bus, "HOME-MENU:TOGGLED", () => this.syncHomeVisibility());

        // Run the clock only while the home workspace is displayed.
        useEffect((visible) => {
            if (!visible) {
                return;
            }
            this.state.workspaceNow = Date.now();
            const timer = browser.setInterval(() => {
                if (!document.hidden) {
                    this.state.workspaceNow = Date.now();
                }
            }, 1000);
            return () => browser.clearInterval(timer);
        }, () => [this.state.homeVisible]);

        // keyboard shortcuts: Alt+Shift (plain Alt+digit switches tabs in Firefox).
        // Alt+Shift+A is Odoo's "Schedule Activity", so the overview uses Alt+Shift+O.
        // A button of the current screen using the same key (data-hotkey) always wins.
        const shortcutAvailable = (key) => () =>
            this.state.settings.shortcuts &&
            !document.querySelector(`[data-hotkey="shift+${key}"], [data-hotkey="alt+shift+${key}"]`);
        useHotkey(`alt+shift+${OVERVIEW_KEY}`, () => this.toggleOverview(), {
            bypassEditableProtection: true,
            global: true,
            isAvailable: shortcutAvailable(OVERVIEW_KEY),
        });
        for (let n = 1; n <= 9; n++) {
            useHotkey(`alt+shift+${n}`, () => this.openPinnedAt(n - 1), {
                bypassEditableProtection: true,
                isAvailable: shortcutAvailable(n),
            });
        }

        // body padding / classes follow the settings
        useEffect(
            () => this.applyBodyLayout(),
            () => [
                this.state.settings.position,
                this.state.settings.style,
                this.state.settings.icon_size,
                this.state.settings.autohide,
                this.state.settings.accent_color,
                this.state.homeVisible,
            ]
        );

        // focus search box when the overview opens
        useEffect(
            (open) => {
                if (open && this.searchRef.el) {
                    this.searchRef.el.focus();
                }
            },
            () => [this.state.overviewOpen]
        );

        // notification badges: refresh now and every minute while the tab is visible
        useEffect(
            (show) => {
                if (!show) {
                    this.state.badges = {};
                    return;
                }
                this.refreshBadges();
                const timer = browser.setInterval(() => {
                    if (!document.hidden) {
                        this.refreshBadges();
                    }
                }, BADGE_REFRESH_MS);
                return () => browser.clearInterval(timer);
            },
            () => [this.state.settings.show_badges]
        );

        this.onDocClick = () => {
            if (this.state.contextMenu) {
                this.state.contextMenu = null;
                this.scheduleHide();
            }
        };
        // capture phase: Odoo's hotkey service handles Escape first otherwise
        this.onKeydown = (ev) => {
            if (ev.key !== "Escape" || !(this.state.contextMenu || this.state.overviewOpen)) {
                return;
            }
            if (document.querySelector(".o_dialog")) {
                return; // a dialog (picker / settings) is on top: let it close first
            }
            ev.preventDefault();
            ev.stopImmediatePropagation();
            if (this.state.contextMenu) {
                this.state.contextMenu = null;
                this.scheduleHide();
            } else {
                this.closeOverview();
            }
        };
        onMounted(() => {
            browser.addEventListener("click", this.onDocClick);
            browser.addEventListener("keydown", this.onKeydown, true);
        });
        onWillUnmount(() => {
            browser.removeEventListener("click", this.onDocClick);
            browser.removeEventListener("keydown", this.onKeydown, true);
            browser.clearTimeout(this.hideTimer);
            const body = document.body;
            body.classList.remove(
                "o_velkio_dock_enabled",
                ...POSITIONS.map((p) => `o_velkio_dock_side_${p.value}`)
            );
            body.style.removeProperty("--o-velkio-dock-space");
        });
    }

    /* ---------------- data ---------------- */
    get workspaceDate() {
        return new Intl.DateTimeFormat(undefined, {
            weekday: "long", month: "long", day: "numeric",
            year: "numeric",
        }).format(new Date(this.state.workspaceNow));
    }

    get workspaceIsLight() {
        return cookie.get("color_scheme") !== "dark";
    }

    get workspaceTime() {
        return new Intl.DateTimeFormat(undefined, {
            hour: "2-digit", minute: "2-digit", second: "2-digit",
        }).format(new Date(this.state.workspaceNow));
    }

    get workspaceGreeting() {
        const hour = new Date(this.state.workspaceNow).getHours();
        const greeting = hour >= 5 && hour < 12 ? _t("Good morning")
            : hour >= 12 && hour < 17 ? _t("Good afternoon")
            : hour >= 17 && hour < 21 ? _t("Good evening") : _t("Good night");
        return user.name ? `${greeting}, ${user.name}` : greeting;
    }

    get workspaceCompany() {
        return user.activeCompany;
    }

    get workspaceCompanyLogo() {
        return this.workspaceCompany
            ? `/web/image/res.company/${this.workspaceCompany.id}/logo` : "";
    }

    get workspaceRecords() {
        return this.overviewRecords.slice(0, 5);
    }

    get allApps() {
        return this.menuService.getApps();
    }

    get appsById() {
        return new Map(this.allApps.map((a) => [a.id, a]));
    }

    badgeFor(id) {
        return this.state.settings.show_badges ? this.state.badges[id] || 0 : 0;
    }

    badgeText(count) {
        return count > 99 ? "99+" : String(count);
    }

    get pinnedApps() {
        const byId = this.appsById;
        return this.state.dockIds
            .filter((id) => byId.has(id))
            .map((id) => ({
                ...toDockApp(byId.get(id)),
                kind: "pinned",
                recent: this.state.recentIds.includes(id),
                badge: this.badgeFor(id),
            }));
    }

    /** Recently opened apps that are NOT pinned (shown after a separator). */
    get recentApps() {
        const s = this.state.settings;
        if (!s.show_recent || !s.recent_limit) {
            return [];
        }
        const byId = this.appsById;
        return this.state.recentIds
            .filter((id) => byId.has(id) && !this.state.dockIds.includes(id))
            .slice(0, s.recent_limit)
            .map((id) => ({
                ...toDockApp(byId.get(id)),
                kind: "recent",
                recent: true,
                badge: this.badgeFor(id),
            }));
    }

    /** Favourite (sub-)menus, with the icon of their app. */
    get favoriteMenus() {
        const byId = this.appsById;
        const result = [];
        for (const id of this.state.favIds) {
            const menu = this.menuService.getMenu(id);
            if (!menu || menu.id === "root") {
                continue;
            }
            const app = byId.get(menu.appID);
            result.push({
                id: menu.id,
                name: app && app.id !== menu.id ? `${app.name} › ${menu.name}` : menu.name,
                shortName: menu.name,
                appName: app ? app.name : "",
                kind: "fav",
                raw: menu,
                href: menuHref(menu),
                ...iconInfo(app || menu),
            });
        }
        return result;
    }

    get dockFavorites() {
        return this.state.settings.show_favorites ? this.favoriteMenus : [];
    }

    isFavorite(menuId) {
        return this.state.favIds.includes(menuId);
    }

    /** Recent apps for the overview screen (pinned or not). */
    get overviewRecent() {
        const byId = this.appsById;
        return this.state.recentIds
            .filter((id) => byId.has(id))
            .slice(0, 8)
            .map((id) => ({
                ...toDockApp(byId.get(id)),
                pinned: this.state.dockIds.includes(id),
                badge: this.badgeFor(id),
            }));
    }

    get overviewRecords() {
        const term = this.state.overviewSearch.trim().toLowerCase();
        const byId = this.appsById;
        return this.state.recentRecords
            .filter(
                (r) =>
                    !term ||
                    r.name.toLowerCase().includes(term) ||
                    (r.model_name || "").toLowerCase().includes(term)
            )
            .map((r) => {
                const app = byId.get(r.app_id);
                return {
                    ...r,
                    key: `${r.model},${r.id}`,
                    href: recordHref(r),
                    appName: app ? app.name : "",
                    ...(app ? iconInfo(app) : RECORD_FALLBACK_ICON),
                };
            });
    }

    get overviewFavorites() {
        const term = this.state.overviewSearch.trim().toLowerCase();
        return this.favoriteMenus.filter((m) => !term || m.name.toLowerCase().includes(term));
    }

    get overviewApps() {
        const term = this.state.overviewSearch.trim().toLowerCase();
        return this.allApps
            .filter((a) => !term || a.name.toLowerCase().includes(term))
            .map((a) => ({
                ...toDockApp(a),
                pinned: this.state.dockIds.includes(a.id),
                badge: this.badgeFor(a.id),
            }));
    }

    /** Sub-menus matching the search, e.g. "Sales / Orders / Quotations". */
    get overviewMenus() {
        const term = this.state.overviewSearch.trim().toLowerCase();
        if (term.length < 2 || !this.menuService.getAll) {
            return [];
        }
        const appIds = new Set(this.allApps.map((a) => a.id));
        const results = [];
        for (const menu of this.menuService.getAll()) {
            if (
                menu.id === "root" ||
                appIds.has(menu.id) ||
                !menu.actionID ||
                !menu.name ||
                !menu.name.toLowerCase().includes(term)
            ) {
                continue;
            }
            const app = this.menuService.getMenu(menu.appID);
            results.push({
                id: menu.id,
                name: menu.name,
                appName: app ? app.name : "",
                raw: menu,
                href: menuHref(menu),
                favorite: this.isFavorite(menu.id),
            });
            if (results.length >= 12) {
                break;
            }
        }
        return results;
    }

    /* ---------------- layout ---------------- */
    get isHorizontal() {
        return ["top", "bottom"].includes(this.state.settings.position);
    }

    get size() {
        return SIZES[this.state.settings.icon_size] || SIZES.medium;
    }

    get thickness() {
        return this.size.item + DOCK_PADDING * 2;
    }

    get dockClass() {
        const s = this.state.settings;
        const cls = [
            "o_velkio_dock",
            "d-print-none",
            `o_velkio_dock_pos_${s.position}`,
            `o_velkio_dock_style_${s.style}`,
            this.isHorizontal ? "o_velkio_dock_horizontal" : "o_velkio_dock_vertical",
        ];
        if (s.magnify) {
            cls.push("o_velkio_dock_magnify");
        }
        if (s.autohide && !this.state.homeVisible) {
            cls.push("o_velkio_dock_autohide");
            if (this.state.revealed || this.state.overviewOpen || this.state.contextMenu) {
                cls.push("o_velkio_dock_revealed");
            }
        }
        return cls.join(" ");
    }

    get dockStyle() {
        const s = this.state.settings;
        return [
            `--dock-item: ${this.size.item}px`,
            `--dock-icon: ${this.size.icon}px`,
            `--dock-thickness: ${this.thickness}px`,
            `--dock-accent: ${s.accent_color || DOCK_DEFAULTS.accent_color}`,
        ].join("; ");
    }

    get overviewIsLight() {
        const theme = this.state.settings.overview_theme;
        if (theme === "auto") {
            return cookie.get("color_scheme") !== "dark";
        }
        return theme === "light";
    }

    get overviewClass() {
        return [
            "o_velkio_dock_overview",
            `o_velkio_dock_overview_${this.state.settings.position}`,
            this.overviewIsLight ? "o_velkio_dock_overview_light" : "o_velkio_dock_overview_dark",
        ].join(" ");
    }

    syncHomeVisibility() {
        // Enterprise supplies the home menu; Community keeps its normal dock.
        this.state.homeVisible = Boolean(this.env.services.home_menu?.hasHomeMenu);
        if (this.state.homeVisible) {
            this.state.tooltip = null;
            this.state.contextMenu = null;
            this.state.overviewOpen = false;
            this.state.revealed = false;
            browser.clearTimeout(this.hideTimer);
        }
    }

    applyBodyLayout() {
        const s = this.state.settings;
        const body = document.body;
        body.classList.remove(...POSITIONS.map((p) => `o_velkio_dock_side_${p.value}`));
        body.classList.add("o_velkio_dock_enabled", `o_velkio_dock_side_${s.position}`);
        let space = this.thickness;
        if (s.style === "floating") {
            space += FLOAT_GAP * 2;
        }
        if (s.autohide && !this.state.homeVisible) {
            space = 0;
        }
        body.style.setProperty("--o-velkio-dock-space", `${space}px`);
        body.style.setProperty("--o-velkio-dock-accent", s.accent_color || DOCK_DEFAULTS.accent_color);
    }

    /** Position for a floating element next to the dock item `rect`. */
    sidePosition(rect, gap) {
        const pos = this.state.settings.position;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        switch (pos) {
            case "right":
                return `right: ${vw - rect.left + gap}px; top: ${rect.top + rect.height / 2}px;`;
            case "top":
                return `left: ${rect.left + rect.width / 2}px; top: ${rect.bottom + gap}px;`;
            case "bottom":
                return `left: ${rect.left + rect.width / 2}px; bottom: ${vh - rect.top + gap}px;`;
            default:
                return `left: ${rect.right + gap}px; top: ${rect.top + rect.height / 2}px;`;
        }
    }

    /* ---------------- tooltip ---------------- */
    showTooltip(ev, text) {
        if (this.state.dragId || this.state.contextMenu) {
            return;
        }
        const rect = ev.currentTarget.getBoundingClientRect();
        // a magnified icon grows towards the tooltip: keep clear of it
        const gap = this.state.settings.magnify ? 10 + Math.round(this.size.item * 0.3) : 10;
        this.state.tooltip = { text, style: this.sidePosition(rect, gap) };
    }

    /** Mouse wheels scroll vertically: turn that into sideways scroll on a top/bottom dock. */
    onItemsWheel(ev) {
        if (!this.isHorizontal || Math.abs(ev.deltaY) <= Math.abs(ev.deltaX)) {
            return;
        }
        const el = ev.currentTarget;
        if (el.scrollWidth > el.clientWidth) {
            ev.preventDefault();
            el.scrollLeft += ev.deltaY;
            this.state.tooltip = null;
        }
    }

    itemTooltip(app) {
        if (app.kind === "pinned" && this.state.settings.shortcuts) {
            const index = this.state.dockIds.indexOf(app.id);
            if (index >= 0 && index < 9) {
                return `${app.name}  (Alt+Shift+${index + 1})`;
            }
        }
        return app.name;
    }

    hideTooltip() {
        this.state.tooltip = null;
    }

    /* ---------------- auto-hide ---------------- */
    reveal() {
        browser.clearTimeout(this.hideTimer);
        this.state.revealed = true;
    }

    scheduleHide() {
        if (!this.state.settings.autohide) {
            return;
        }
        browser.clearTimeout(this.hideTimer);
        this.hideTimer = browser.setTimeout(() => {
            if (!this.state.contextMenu && !this.state.dragId) {
                this.state.revealed = false;
            }
        }, 500);
    }

    /* ---------------- badges ---------------- */
    async refreshBadges() {
        if (!this.state.settings.show_badges || this.badgesLoading) {
            return;
        }
        this.badgesLoading = true;
        try {
            this.state.badges = await this.orm.silent.call("velkio.dock.item", "get_badges", []);
        } catch {
            // badges are best effort
        } finally {
            this.badgesLoading = false;
        }
    }

    /* ---------------- recent apps ---------------- */
    updateCurrentApp() {
        const app = this.menuService.getCurrentApp();
        const id = app ? app.id : null;
        this.state.currentAppId = id;
        if (id && this.state.recentIds[0] !== id) {
            this.state.recentIds = [id, ...this.state.recentIds.filter((r) => r !== id)].slice(
                0,
                RECENT_MAX
            );
            this.orm.silent.call("velkio.dock.item", "push_recent", [id]).catch(() => {});
        }
    }

    removeRecent(app) {
        this.state.contextMenu = null;
        this.state.recentIds = this.state.recentIds.filter((id) => id !== app.id);
        this.orm.call("velkio.dock.item", "remove_recent", [app.id]).catch(() => {});
    }

    async clearRecent() {
        this.state.contextMenu = null;
        this.state.recentIds = [];
        await this.orm.call("velkio.dock.item", "clear_recent", []);
        this.notification.add(_t("Recent apps cleared."), { type: "success" });
    }

    /* ---------------- recent records ---------------- */
    pushRecentRecord({ model, id, name }) {
        const first = this.state.recentRecords[0];
        if (first && first.model === model && first.id === id && first.name === name) {
            return;
        }
        const appId = this.state.currentAppId;
        const entry = { model, id, name, app_id: appId, model_name: "" };
        const previous = this.state.recentRecords.find((r) => r.model === model && r.id === id);
        if (previous) {
            entry.model_name = previous.model_name;
        }
        this.state.recentRecords = [
            entry,
            ...this.state.recentRecords.filter((r) => !(r.model === model && r.id === id)),
        ].slice(0, RECENT_RECORDS_MAX);
        this.orm.silent
            .call("velkio.dock.item", "push_recent_record", [{ model, id, name, app_id: appId }])
            .then((saved) => {
                if (saved) {
                    Object.assign(entry, saved);
                    const index = this.state.recentRecords.findIndex(
                        (r) => r.model === model && r.id === id
                    );
                    if (index >= 0) {
                        this.state.recentRecords[index] = { ...saved };
                    }
                }
            })
            .catch(() => {});
    }

    openRecord(record) {
        this.state.overviewOpen = false;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: record.model,
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onRecordClick(ev, record) {
        if (isNewTabClick(ev)) {
            return;
        }
        ev.preventDefault();
        this.openRecord(record);
    }

    removeRecentRecord(record) {
        this.state.recentRecords = this.state.recentRecords.filter(
            (r) => !(r.model === record.model && r.id === record.id)
        );
        this.orm.call("velkio.dock.item", "remove_recent_record", [record.model, record.id]);
    }

    async clearRecentRecords() {
        this.state.recentRecords = [];
        await this.orm.call("velkio.dock.item", "clear_recent_records", []);
        this.notification.add(_t("Recent records cleared."), { type: "success" });
    }

    /* ---------------- favourite menus ---------------- */
    async saveFavorites(ids) {
        this.state.favIds = ids;
        try {
            this.state.favIds = await this.orm.call("velkio.dock.item", "set_favorites", [ids]);
        } catch (e) {
            this.notification.add(_t("Could not save favourite menus."), { type: "danger" });
            throw e;
        }
    }

    toggleFavorite(menu) {
        this.state.contextMenu = null;
        const ids = this.isFavorite(menu.id)
            ? this.state.favIds.filter((id) => id !== menu.id)
            : [...this.state.favIds, menu.id];
        return this.saveFavorites(ids);
    }

    moveFavorite(menu, delta) {
        this.state.contextMenu = null;
        const ids = [...this.state.favIds];
        const i = ids.indexOf(menu.id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= ids.length) {
            return;
        }
        [ids[i], ids[j]] = [ids[j], ids[i]];
        this.saveFavorites(ids);
    }

    /* ---------------- persistence ---------------- */
    async persist(ids) {
        this.state.dockIds = ids;
        try {
            await this.orm.call("velkio.dock.item", "set_dock", [ids]);
        } catch (e) {
            this.notification.add(_t("Could not save the dock layout."), { type: "danger" });
            throw e;
        }
    }

    async saveSettings(settings) {
        this.state.settings = { ...DOCK_DEFAULTS, ...settings };
        const saved = await this.orm.call("velkio.dock.item", "set_settings", [settings]);
        this.state.settings = { ...DOCK_DEFAULTS, ...saved };
        this.notification.add(_t("Dock settings saved."), { type: "success" });
    }

    /* ---------------- actions ---------------- */
    openApp(app) {
        this.state.contextMenu = null;
        this.state.tooltip = null;
        this.state.overviewOpen = false;
        this.menuService.selectMenu(app.raw);
    }

    /** Plain click opens in place; Ctrl/Cmd/Shift/middle click is left to the browser. */
    onAppClick(ev, app) {
        if (isNewTabClick(ev)) {
            this.state.tooltip = null;
            return;
        }
        ev.preventDefault();
        this.openApp(app);
    }

    openInNewTab(item) {
        this.state.contextMenu = null;
        browser.open(item.href, "_blank");
    }

    openPinnedAt(index) {
        const app = this.pinnedApps[index];
        if (app) {
            this.openApp(app);
        }
    }

    openMenu(menu) {
        this.state.overviewOpen = false;
        this.menuService.selectMenu(menu.raw);
    }

    onMenuClick(ev, menu) {
        if (isNewTabClick(ev)) {
            return;
        }
        ev.preventDefault();
        this.openMenu(menu);
    }

    toggleOverview() {
        this.state.tooltip = null;
        this.state.contextMenu = null;
        this.state.overviewSearch = "";
        this.state.overviewOpen = !this.state.overviewOpen;
        if (this.state.overviewOpen) {
            this.refreshBadges();
        }
    }

    closeOverview() {
        this.state.overviewOpen = false;
        this.scheduleHide();
    }

    onOverviewSearchKeydown(ev) {
        if (ev.key === "Enter") {
            const app = this.overviewApps[0];
            if (app) {
                this.openApp(app);
                return;
            }
            const fav = this.overviewFavorites[0];
            if (fav) {
                this.openApp(fav);
                return;
            }
            const menu = this.overviewMenus[0];
            if (menu) {
                this.openMenu(menu);
                return;
            }
            const record = this.overviewRecords[0];
            if (record) {
                this.openRecord(record);
            }
        }
    }

    openOdooHome() {
        this.state.overviewOpen = false;
        const homeMenu = this.env.services.home_menu; // Odoo Enterprise
        if (homeMenu && homeMenu.toggle) {
            homeMenu.toggle(true);
        } else {
            browser.location.href = "/odoo";
        }
    }

    openPicker() {
        this.state.contextMenu = null;
        this.state.tooltip = null;
        this.state.overviewOpen = false;
        this.dialog.add(VelkioDockPicker, {
            apps: this.allApps.map(toDockApp),
            selectedIds: [...this.state.dockIds],
            onSave: (ids) => {
                const kept = this.state.dockIds.filter((id) => ids.includes(id));
                const added = ids.filter((id) => !kept.includes(id));
                return this.persist([...kept, ...added]);
            },
        });
    }

    openSettings() {
        this.state.contextMenu = null;
        this.state.tooltip = null;
        this.state.overviewOpen = false;
        this.dialog.add(VelkioDockSettings, {
            settings: { ...this.state.settings },
            onPreview: (settings) => {
                this.state.settings = { ...DOCK_DEFAULTS, ...settings };
            },
            onSave: (settings) => this.saveSettings(settings),
            onClearRecent: () => this.clearRecent(),
            onClearRecentRecords: () => this.clearRecentRecords(),
        });
    }

    onContextMenu(ev, app) {
        this.state.tooltip = null;
        const rect = ev.currentTarget.getBoundingClientRect();
        const pos = this.state.settings.position;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        let style;
        switch (pos) {
            case "right":
                style = `right: ${vw - rect.left + 8}px; top: ${Math.min(rect.top, vh - 320)}px;`;
                break;
            case "top":
                style = `left: ${Math.min(rect.left, vw - 240)}px; top: ${rect.bottom + 8}px;`;
                break;
            case "bottom":
                style = `left: ${Math.min(rect.left, vw - 240)}px; bottom: ${vh - rect.top + 8}px;`;
                break;
            default:
                style = `left: ${rect.right + 8}px; top: ${Math.min(rect.top, vh - 320)}px;`;
        }
        this.state.contextMenu = { app, kind: app.kind, style };
        this.reveal();
    }

    pin(app) {
        this.state.contextMenu = null;
        if (!this.state.dockIds.includes(app.id)) {
            this.persist([...this.state.dockIds, app.id]);
        }
    }

    unpin(app) {
        this.state.contextMenu = null;
        this.persist(this.state.dockIds.filter((id) => id !== app.id));
    }

    togglePin(app) {
        if (this.state.dockIds.includes(app.id)) {
            this.unpin(app);
        } else {
            this.pin(app);
        }
    }

    move(app, delta) {
        this.state.contextMenu = null;
        const ids = [...this.state.dockIds];
        const i = ids.indexOf(app.id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= ids.length) {
            return;
        }
        [ids[i], ids[j]] = [ids[j], ids[i]];
        this.persist(ids);
    }

    /* ---------------- drag & drop (pinned + recent → pin) ---------------- */
    onDragStart(ev, app) {
        if (app.kind === "fav") {
            ev.preventDefault();
            return;
        }
        this.state.tooltip = null;
        this.state.dragId = app.id;
        this.state.dragKind = app.kind;
        this.state.dropTargetId = null;
        this.dragStartOrder = [...this.state.dockIds];
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(app.id));
    }

    /** Hovering a pinned icon (or the + button when target is null). */
    onDragOver(ev, app) {
        const dragId = this.state.dragId;
        if (!dragId) {
            return;
        }
        ev.dataTransfer.dropEffect = "move";
        if (this.state.dragKind === "recent") {
            // recent app: just highlight where it will be pinned
            this.state.dropTargetId = app ? app.id : "end";
            return;
        }
        if (!app || dragId === app.id || app.kind !== "pinned") {
            return;
        }
        // pinned app: live reorder
        const ids = [...this.state.dockIds];
        const from = ids.indexOf(dragId);
        const to = ids.indexOf(app.id);
        if (from < 0 || to < 0) {
            return;
        }
        ids.splice(from, 1);
        ids.splice(to, 0, dragId);
        this.state.dockIds = ids;
    }

    onDragLeave() {
        if (this.state.dragKind === "recent") {
            this.state.dropTargetId = null;
        }
    }

    /** Drop on a pinned icon (app) or on the + button (app = null). */
    onDrop(app) {
        const dragId = this.state.dragId;
        if (!dragId) {
            return;
        }
        let ids = [...this.state.dockIds];
        if (this.state.dragKind === "recent" && !ids.includes(dragId)) {
            const target = app && app.kind === "pinned" ? ids.indexOf(app.id) : -1;
            if (target >= 0) {
                ids.splice(target, 0, dragId);
            } else {
                ids.push(dragId);
            }
        }
        this.resetDrag();
        if (JSON.stringify(this.dragStartOrder || []) !== JSON.stringify(ids)) {
            this.persist(ids);
        }
    }

    onDragEnd() {
        if (!this.state.dragId) {
            return;
        }
        // dropped outside the dock: keep the reorder done so far for pinned apps
        const ids = [...this.state.dockIds];
        const changed = JSON.stringify(this.dragStartOrder || []) !== JSON.stringify(ids);
        this.resetDrag();
        if (changed) {
            this.persist(ids);
        }
    }

    resetDrag() {
        this.state.dragId = null;
        this.state.dragKind = null;
        this.state.dropTargetId = null;
        this.scheduleHide();
    }
}

registry.category("main_components").add("velkio_odoo_dock.VelkioDock", {
    Component: VelkioDock,
});
