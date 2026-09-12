/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { reactive } from "@odoo/owl";

// Safety net for when the websocket cannot be reached (proxy, offline laptop).
// With the bus working this rarely brings back anything new.
const FALLBACK_POLL_MS = 60000;

/**
 * Holds every popup currently on screen, for the whole web client.
 *
 * bus_service is taken as a service dependency rather than through
 * useService(): on Odoo 17 it is declared `async: true`, which makes
 * useService() throw.
 */
export const velkioNotificationService = {
    dependencies: ["rpc", "bus_service", "velkio_sound"],

    start(env, { rpc, bus_service: busService, velkio_sound: sound }) {
        const state = reactive({ popups: [], count: 0 });
        let seq = 0;

        /**
         * Publish the waiting count.
         *
         * Two places show it: the bell in the top bar reads state.count
         * directly, and the app tile on the home screen picks it up from a CSS
         * custom property. The tile is drawn by the web client itself, so a
         * pseudo-element fed by a variable is the only way to badge it without
         * reaching into a DOM that OWL owns.
         */
        function setCount(value) {
            const n = Math.max(0, value || 0);
            state.count = n;
            const root = document.documentElement;
            // `none` suppresses the pseudo-element entirely, so nothing is
            // drawn when there is nothing waiting.
            root.style.setProperty(
                "--velkio-badge", n > 0 ? `"${n > 99 ? "99+" : n}"` : "none"
            );
        }
        // Notices we have already armed a timer for, so a refresh does not
        // schedule the same one twice.
        const armed = new Map();
        // Ids already sent to the operating system, so one reminder is never
        // announced twice. The notifications themselves are deliberately left
        // alone afterwards: the system notification list is a record of what
        // happened, and closing them from here would erase that record.
        const desktopSent = new Set();
        // Answered in this tab. A catch-up replay must never bring one of
        // these back: the server is the authority, but a reply that has not
        // landed yet would otherwise let the next poll re-open it.
        const dismissed = new Set();
        // Ids being put off right now. The card calls snooze and only then
        // plays its leave animation, so the removal that follows must not
        // record them as dismissed.
        const snoozing = new Set();

        /**
         * @param {Object} payload popup data built by the server
         * @param {boolean} live true for a live push, false when replaying
         */
        function show(payload, live) {
            if (!payload || !payload.id) {
                return false;
            }
            if (!live && dismissed.has(payload.id)) {
                return false;
            }
            const at = state.popups.findIndex((p) => p.id === payload.id);
            const popup = { ...payload, key: `${payload.id}-${seq++}` };
            if (at !== -1) {
                // Already on screen: refresh the content, but do not chime
                // again just because the server pushed what we already showed.
                state.popups.splice(at, 1, popup);
                return false;
            }
            // Remember whether this arrived now or is a replay of something
            // that fired while the person was away. A backlog must not take
            // over the screen.
            popup.replayed = !live;
            state.popups.push(popup);
            // Replaying a backlog after a page reload should stay silent.
            if (live) {
                if (payload.sound) {
                    sound.play(payload.level);
                }
                showDesktop(payload);
            }
            return true;
        }

        /**
         * Put a notice on screen at the exact moment it falls due.
         *
         * The cron only ticks once a minute, which would make a popup up to a
         * minute late. Instead the server says how long is left, the browser
         * counts that down, and asks the server to confirm before showing
         * anything, so a cancelled notice never appears.
         */
        function arm(entry) {
            if (!entry || !entry.id || armed.has(entry.id)) {
                return;
            }
            const handle = browser.setTimeout(async () => {
                armed.delete(entry.id);
                try {
                    const res = await rpc("/velkio/notification/fire", {
                        notification_id: entry.id,
                    });
                    if (res && res.ok) {
                        show(res.popup, true);
                        if (typeof res.count === "number") {
                            setCount(res.count);
                        }
                    }
                } catch (e) {
                    // The next refresh will pick it up again.
                }
            }, entry.delay_ms);
            armed.set(entry.id, handle);
        }

        function remove(id) {
            if (snoozing.has(id)) {
                snoozing.delete(id);
            } else {
                dismissed.add(id);
            }
            const at = state.popups.findIndex((p) => p.id === id);
            if (at !== -1) {
                state.popups.splice(at, 1);
            }
            // The matching system notification is left in place on purpose, so
            // it stays in the notification list after the popup is answered.
        }

        /**
         * Mirror the reminder into the operating system's own notification
         * area, so it is seen even when Odoo is not the window in front.
         *
         * Only fires when the reader asked for it and the browser has been
         * granted permission; it never prompts on its own, because browsers
         * require a real click for that (see the popup's "Enable" link).
         */
        function showDesktop(payload) {
            const Notif = browser.Notification;
            if (!Notif || !payload.desktop || Notif.permission !== "granted") {
                return;
            }
            if (desktopSent.has(payload.id)) {
                return; // already announced; do not ring twice
            }
            try {
                const native = new Notif(payload.title, {
                    body: payload.desktop_body || "",
                    icon: payload.icon || undefined,
                    // A stable tag keeps a re-send from stacking up copies.
                    tag: `velkio-${payload.id}`,
                    requireInteraction: !!payload.require_ack,
                    silent: !payload.sound,
                });
                native.onclick = () => {
                    window.focus();
                };
                desktopSent.add(payload.id);
            } catch (e) {
                // A blocked or unsupported notification must never break the popup.
            }
        }

        /** Ask the operating system for permission. Needs a real click. */
        async function requestDesktopPermission() {
            const Notif = browser.Notification;
            if (!Notif) {
                return "unsupported";
            }
            if (Notif.permission !== "default") {
                return Notif.permission;
            }
            try {
                return await Notif.requestPermission();
            } catch (e) {
                return Notif.permission;
            }
        }

        async function call(route, id, extra = {}) {
            try {
                // done_all is about the whole list, so it passes no id.
                const params = id === null
                    ? { ...extra }
                    : { notification_id: id, ...extra };
                const res = await rpc(route, params);
                if (res && typeof res.count === "number") {
                    setCount(res.count);
                }
                return res;
            } catch (e) {
                // A failed click must never leave a popup stuck on screen.
                return { success: false };
            }
        }

        /** Ask the server for anything waiting, and for what is about to be. */
        async function refresh() {
            try {
                const res = await rpc("/velkio/notification/pending", {});
                setCount(res.count);
                for (const payload of res.popups || []) {
                    show(payload, false);
                }
                for (const entry of res.upcoming || []) {
                    arm(entry);
                }
            } catch (e) {
                // Keep whatever is already on screen.
            }
        }

        // Live push. The server targets the partner, so every device and tab
        // signed in to this account receives it.
        busService.subscribe("velkio_notification", (payload) => {
            if (show(payload, true)) {
                setCount(state.count + 1);
            }
        });
        // Read somewhere else — in the list, or on another device. The bell
        // follows without waiting for the next poll.
        busService.subscribe("velkio_notification_count", (payload) => {
            if (payload && typeof payload.count === "number") {
                setCount(payload.count);
            }
        });
        // Answered somewhere else: take it down here too.
        busService.subscribe("velkio_notification_close", (payload) => {
            if (!payload || !payload.id) {
                return;
            }
            remove(payload.id);
            // The server sends the real figure: a card taken off the screen
            // is not always one fewer unread.
            setCount(
                typeof payload.count === "number"
                    ? payload.count
                    : state.count - 1
            );
        });

        refresh();

        const isVisible = () => document.visibilityState === "visible";
        document.addEventListener("visibilitychange", () => {
            if (isVisible()) {
                refresh();
            }
        });
        browser.setInterval(() => {
            if (isVisible()) {
                refresh();
            }
        }, FALLBACK_POLL_MS);

        return {
            state,
            refresh,
            close: remove,
            requestDesktopPermission,
            desktopPermission: () =>
                browser.Notification ? browser.Notification.permission : "unsupported",
            markSeen: (id) => call("/velkio/notification/seen", id),
            done: (id, acknowledged) =>
                call("/velkio/notification/done", id, { acknowledged }),
            /**
             * Clear the screen without reading anything.
             *
             * The server says which ones it actually took down, so a notice
             * that has to be acknowledged stays where it is. Everything else
             * stays unread and keeps its place in the bell.
             */
            closeAll: async () => {
                const res = await call("/velkio/notification/dismiss_all", null);
                if (res && res.success) {
                    for (const id of res.dismissed || []) {
                        remove(id);
                    }
                }
                return res;
            },
            snooze: (id, minutes) => {
                // Putting one off is not dismissing it: it is due to return,
                // and a device that was closed at that moment picks it up on
                // its next catch-up.
                snoozing.add(id);
                dismissed.delete(id);
                return call("/velkio/notification/snooze", id, { minutes });
            },
        };
    },
};

registry.category("services").add("velkio_notification", velkioNotificationService);
