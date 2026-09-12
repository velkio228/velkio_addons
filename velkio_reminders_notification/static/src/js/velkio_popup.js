/** @odoo-module **/

import {
    Component,
    useState,
    onWillStart,
    onWillDestroy,
    useExternalListener,
    markup,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";

// Fallback only: the real limit comes from the configured style.
const DEFAULT_VISIBLE = 1;
// Rough height of a card plus its gap. Used only to work out how many can
// physically fit, so a high stack limit can never run off the screen.
const CARD_HEIGHT = 240;
const LEVEL_RANK = { urgent: 3, warning: 2, info: 1 };
// Keep in step with the leave animation in velkio_popup.scss.
const LEAVE_MS = 200;
const SNOOZE_CHOICES = [5, 10, 30, 60];

const SHADOWS = {
    none: "none",
    soft: "0 2px 6px rgba(15,23,42,.06), 0 8px 20px -8px rgba(15,23,42,.16)",
    deep: "0 1px 2px rgba(15,23,42,.06), 0 12px 24px -8px rgba(15,23,42,.18), 0 32px 56px -16px rgba(15,23,42,.22)",
};

// ────────────────────────────────────────────────────────────────
// ONE POPUP
// ────────────────────────────────────────────────────────────────
export class VelkioPopupCard extends Component {
    static template = "velkio_reminders_notification.PopupCard";
    static props = ["data", "onClose", "onDone", "onSnooze", "onSeen"];

    setup() {
        this.notifications = useService("velkio_notification");
        this.state = useState({
            countdown: this.props.data.duration || 0,
            leaving: false,
            busy: false,
            snoozeOpen: false,
            // "default" means the browser has neither granted nor refused yet.
            desktopPermission: this.notifications.desktopPermission(),
        });
        this.snoozeChoices = SNOOZE_CHOICES;
        this._timer = null;

        onWillStart(() => this.props.onSeen(this.props.data.id));

        if (this.props.data.duration > 0) {
            this._timer = browser.setInterval(() => this._tick(), 1000);
        }
        onWillDestroy(() => this._stopTimer());
    }

    _tick() {
        this.state.countdown--;
        if (this.state.countdown <= 0) {
            // Stop either way, so a popup awaiting acknowledgement does not
            // keep firing this callback once the bar has run out.
            this._stopTimer();
            if (!this.props.data.require_ack) {
                this.onClose();
            }
        }
    }

    _stopTimer() {
        if (this._timer) {
            browser.clearInterval(this._timer);
            this._timer = null;
        }
    }

    async _leave() {
        this._stopTimer();
        this.state.leaving = true;
        await new Promise((resolve) => browser.setTimeout(resolve, LEAVE_MS));
        this.props.onClose(this.props.data.id);
    }

    get style() {
        return this.props.data.style || {};
    }

    /**
     * Offer to switch on system notifications, but only where it makes sense:
     * the reader wants them, and the browser has not been asked yet. Browsers
     * only accept the request from a real click, which is why this is a link
     * rather than something automatic.
     */
    get canOfferDesktop() {
        return (
            this.props.data.desktop &&
            this.state.desktopPermission === "default" &&
            !this.props.data.preview
        );
    }

    async enableDesktop() {
        this.state.desktopPermission =
            await this.notifications.requestDesktopPermission();
    }

    get rootClass() {
        const style = this.style;
        const classes = [
            "velkio-popup",
            `velkio-skin-${style.skin || "card"}`,
            `velkio-level-${this.props.data.level || "info"}`,
            `velkio-surface-${style.surface || "solid"}`,
            `velkio-anim-${style.animation || "drop"}`,
        ];
        if (style.appearance === "dark") {
            classes.push("velkio-dark");
        } else if (style.appearance === "light") {
            classes.push("velkio-light");
        }
        // "auto" adds neither, so the stylesheet's media query decides.
        if (style.compact) {
            classes.push("velkio-compact");
        }
        if (this.state.leaving) {
            classes.push("is-leaving");
        }
        return classes.join(" ");
    }

    /** The configured look, handed to CSS as custom properties. */
    get rootStyle() {
        const style = this.style;
        const level = this.props.data.level || "info";
        const colors = style.colors || {};
        const accent =
            style.accent_mode === "custom"
                ? style.accent_color
                : colors[level] || colors.info;
        const parts = [
            `--v-a: ${accent || "#2563eb"}`,
            `--v-radius: ${style.radius === undefined ? 16 : style.radius}px`,
            `--v-shadow: ${SHADOWS[style.shadow] || SHADOWS.deep}`,
        ];
        return parts.join("; ") + ";";
    }

    get showIcon() {
        return this.style.show_icon !== false;
    }

    get showChip() {
        return this.style.show_level_chip !== false;
    }

    get showAuthor() {
        return this.style.show_author !== false;
    }

    get showProgress() {
        return this.style.show_progress !== false && this.props.data.duration > 0;
    }

    get icon() {
        return {
            info: "fa-info-circle",
            warning: "fa-exclamation-circle",
            urgent: "fa-exclamation-triangle",
        }[this.props.data.level] || "fa-bell";
    }

    /**
     * The friendly designs lead with a bell; the alert designs lead with the
     * symbol for the level, which is what makes them read as warnings.
     */
    get heroIcon() {
        const skin = this.style.skin || "card";
        if (skin === "card" || skin === "neumorph") {
            return "fa-bell";
        }
        return this.icon;
    }

    /**
     * The message is an HTML field, sanitized server side. It has to be marked
     * as markup, otherwise t-out escapes the tags and shows them as text.
     */
    get bodyMarkup() {
        return markup(this.props.data.body || "");
    }

    get levelLabel() {
        return {
            info: _t("Information"),
            warning: _t("Important"),
            urgent: _t("Urgent"),
        }[this.props.data.level] || _t("Information");
    }

    get subtitle() {
        return this.props.data.is_self ? _t("Your reminder") : this.props.data.author;
    }

    /** Close without acknowledging. */
    async onClose() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        await this.props.onDone(this.props.data.id, false);
        this._leave();
    }

    /** Explicitly acknowledge. */
    async onAcknowledge() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        await this.props.onDone(this.props.data.id, true);
        this._leave();
    }

    async onSnooze(minutes) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        await this.props.onSnooze(this.props.data.id, minutes);
        this._leave();
    }

    toggleSnooze() {
        this.state.snoozeOpen = !this.state.snoozeOpen;
    }

    snoozeLabel(minutes) {
        return minutes >= 60 ? `${minutes / 60} h` : `${minutes} min`;
    }
}

// ────────────────────────────────────────────────────────────────
// THE LAYER THAT SITS ON EVERY SCREEN
// ────────────────────────────────────────────────────────────────
export class VelkioPopupManager extends Component {
    static template = "velkio_reminders_notification.PopupManager";
    static components = { VelkioPopupCard };
    static props = {};

    setup() {
        this.notifications = useService("velkio_notification");
        this.action = useService("action");
        this.state = useState(this.notifications.state);
        // The manager's own flag, kept out of the shared service state.
        this.ui = useState({ clearing: false });

        // Esc closes the newest popup that is not waiting for an answer.
        useExternalListener(browser, "keydown", (ev) => {
            if (ev.key !== "Escape") {
                return;
            }
            const closable = this.visiblePopups.filter((p) => !p.require_ack);
            const last = closable[closable.length - 1];
            if (last) {
                this.done(last.id, false);
                this.close(last.id);
            }
        });
    }

    get limit() {
        const last = this.state.popups[this.state.popups.length - 1];
        const configured = last && last.style && last.style.stack_limit;
        const wanted = configured || DEFAULT_VISIBLE;
        // Whatever is configured, never put out more cards than the window can
        // hold: the last one would be cut off by the bottom of the screen.
        const height = (typeof window !== "undefined" && window.innerHeight) || 900;
        const fits = Math.max(1, Math.floor((height - 160) / CARD_HEIGHT));
        return Math.min(wanted, fits);
    }

    /**
     * What actually goes on screen.
     *
     * Anything that just arrived is shown. A backlog waiting from previous
     * days is represented by its most recent item only — signing in after a
     * few away should not bury the screen under a wall of cards. The rest are
     * counted on the chip underneath, and in the bell.
     */
    get visiblePopups() {
        // Most urgent first; among equals the oldest, so a queue is worked
        // through in order rather than newest-first. Sort is stable, so equal
        // levels keep the order they arrived in.
        const byImportance = (list) =>
            [...list].sort(
                (a, b) => (LEVEL_RANK[b.level] || 0) - (LEVEL_RANK[a.level] || 0)
            );
        const live = byImportance(this.state.popups.filter((p) => !p.replayed));
        const replayed = byImportance(this.state.popups.filter((p) => p.replayed));
        const shown = live.slice(0, this.limit);
        if (shown.length < this.limit && replayed.length) {
            // A backlog gets one slot, and the most urgent of it takes that.
            shown.push(replayed[0]);
        }
        return shown;
    }

    get hiddenCount() {
        return Math.max(0, this.state.popups.length - this.visiblePopups.length);
    }

    /**
     * Offer to clear the screen once there is more than one, and only when
     * something can actually go: a card that needs acknowledging stays put.
     */
    get showCloseAll() {
        return (
            this.state.popups.length > 1 &&
            this.state.popups.some((p) => !p.require_ack)
        );
    }

    /**
     * Take the cards off the screen. Nothing is read or answered by this, so
     * the bell keeps counting them until they are opened.
     */
    async closeAll() {
        if (this.ui.clearing) {
            return;
        }
        this.ui.clearing = true;
        try {
            await this.notifications.closeAll();
        } finally {
            this.ui.clearing = false;
        }
    }

    /** Open the full list so the person can work through the backlog. */
    async openWaiting() {
        await this.action.doAction(
            "velkio_reminders_notification.action_velkio_my_notifications"
        );
        this.notifications.refresh();
    }

    /**
     * One stack per configured corner. Without this, popups asking for
     * different positions would all pile onto the same coordinates.
     */
    get stacks() {
        const byPosition = new Map();
        for (const popup of this.visiblePopups) {
            const style = popup.style || {};
            const position = style.position || "top-right";
            if (!byPosition.has(position)) {
                byPosition.set(position, { position, popups: [], width: style.width || 400 });
            }
            byPosition.get(position).popups.push(popup);
        }
        const stacks = [...byPosition.values()];
        if (stacks.length && this.hiddenCount) {
            stacks[stacks.length - 1].showOverflow = true;
        }
        return stacks;
    }

    stackStyle(stack) {
        return `--v-width: ${stack.width}px;`;
    }

    close(id) {
        this.notifications.close(id);
    }

    markSeen(id) {
        return this.notifications.markSeen(id);
    }

    done(id, acknowledged) {
        return this.notifications.done(id, acknowledged);
    }

    snooze(id, minutes) {
        return this.notifications.snooze(id, minutes);
    }
}

// Registered as a main component, so it is mounted once for the whole web
// client and shows up over every screen, whatever the user is doing.
registry.category("main_components").add("VelkioPopupManager", {
    Component: VelkioPopupManager,
    props: {},
});
