/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Overview of everything on the calendar: what is due today, what is waiting,
 * what was flagged, and what has already been answered.
 *
 * The buckets and their domains come from the server, so the list a tile opens
 * is exactly the set that was counted on it.
 */
export class VelkioDashboard extends Component {
    static template = "velkio_reminders_notification.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ buckets: [], nextUp: [], loading: true });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "velkio.notification", "get_dashboard_data", []
            );
            this.state.buckets = data.buckets || [];
            this.state.nextUp = data.next_up || [];
        } finally {
            this.state.loading = false;
        }
    }

    openBucket(bucket) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: bucket.label,
            res_model: "velkio.notification",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: bucket.domain,
            context: { default_audience: "me" },
        });
    }

    openRecord(row) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "velkio.notification",
            res_id: row.id,
            views: [[false, "form"]],
        });
    }

    newReminder() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Reminder"),
            res_model: "velkio.notification",
            views: [[false, "form"]],
            context: { default_audience: "me" },
        });
    }

    /** Their own reminders laid out by date. */
    openCalendar() {
        this.action.doAction("velkio_reminders_notification.action_velkio_calendar");
    }

    openTemplates() {
        this.action.doAction("velkio_reminders_notification.action_velkio_templates");
    }

    levelLabel(level) {
        return {
            info: _t("Information"),
            warning: _t("Important"),
            urgent: _t("Urgent"),
        }[level] || _t("Information");
    }

    /** "Today 15:40" / "Tue 09:00", in the reader's own locale. */
    whenLabel(value) {
        if (!value) {
            return "";
        }
        // The server sends naive UTC; luxon is already available in Odoo.
        const dt = luxon.DateTime.fromSQL(value, { zone: "utc" }).toLocal();
        const today = luxon.DateTime.local().startOf("day");
        const sameDay = dt.startOf("day").equals(today);
        return sameDay
            ? `${_t("Today")} ${dt.toFormat("HH:mm")}`
            : dt.toFormat("ccc dd LLL, HH:mm");
    }
}

registry.category("actions").add("velkio_dashboard", VelkioDashboard);
