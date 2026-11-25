/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Bell in the top bar. It reads the same service as the popups, so the count
 * is live without any polling of its own.
 */
export class ZenvioSystrayItem extends Component {
    static template = "zenvio_reminders_notification.SystrayIcon";
    static props = {};

    setup() {
        this.action = useService("action");
        this.notifications = useService("zenvio_notification");
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
            "zenvio_reminders_notification.action_zenvio_my_notifications"
        );
        this.notifications.refresh();
    }
}

registry.category("systray").add("zenvio_systray", {
    Component: ZenvioSystrayItem,
});
