/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * The read marker: an eye that opens when a notice has been read.
 *
 * Clicking it toggles, so something opened by accident can be put back to
 * unread. It writes through the record like any other field, which keeps the
 * list, the count and the form in step without a reload.
 */
export class VelkioReadEye extends Component {
    static template = "velkio_reminders_notification.ReadEye";
    static props = { ...standardFieldProps };

    get isRead() {
        return !!this.props.record.data[this.props.name];
    }

    get title() {
        return this.isRead
            ? "Read — click to mark unread"
            : "Unread — click to mark read";
    }

    async onClick(ev) {
        // The row would open the record otherwise.
        ev.stopPropagation();
        ev.preventDefault();
        // Deliberately not gated on readonly: the read mark belongs to the
        // reader, so it stays clickable on a notice they may not edit.
        const record = this.props.record;
        // is_read is computed, not stored, so a plain field write never makes
        // it into the changes a read-only list saves — the eye would flip on
        // screen and nowhere else. Calling the model is explicit and works the
        // same from the list and the form.
        await record.model.orm.call(
            record.resModel, "action_toggle_read", [[record.resId]]
        );
        await record.load();
        record.model.notify();
    }
}

export const velkioReadEye = {
    component: VelkioReadEye,
    displayName: "Read Marker",
    supportedTypes: ["boolean"],
};

registry.category("fields").add("velkio_read_eye", velkioReadEye);
