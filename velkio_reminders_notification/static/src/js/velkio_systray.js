/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Bell in the top bar. It reads the same service as the popups, so the count
 * is live without any polling of its own.
 */
export class VelkioSystrayItem extends Component {
    static template = "velkio_reminders_notification.SystrayIcon";
    static props = {};

    setup() {
        this.action = useService("action");
        this.notifications = useService("velkio_notification");
        this.state = useState(this.notifications.state);
    }

    get count() {
        return this.state.count;
    }

    get badge() {
        return this.count > 99 ? "99+" : this.count;
    }

    async openList() {
        await this.action.doAction(
            "velkio_reminders_notification.action_velkio_my_notifications"
        );
        this.notifications.refresh();
    }
}

registry.category("systray").add("velkio_systray", {
    Component: VelkioSystrayItem,
});
