/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { FormRenderer } from "@web/views/form/form_renderer";
import { onWillStart, onWillUnmount, useEffect, useRef } from "@odoo/owl";

/**
 * Hide the chatter's "Send message" / "Log note" / "Activities" buttons per
 * user & model, driven by ``access.management.get_chatter_hide_details``.
 *
 * This stays a ``@web``-only patch (no ``@mail`` import / no template
 * inheritance) so the module keeps ``depends: ['web']`` and degrades to a
 * no-op when ``mail`` is not installed - exactly like the Odoo 17 version.
 * Unlike Odoo 17 it no longer parses ``window.location.hash`` (Odoo 18 is
 * path-based): the model comes from ``record.resModel`` and the company is
 * resolved server-side.
 *
 * ``get_chatter_hide_details`` returns ``hide_*`` = ``true`` when the button
 * must stay VISIBLE (legacy naming), ``false`` when it must be hidden.
 */
const BTN_SELECTORS = {
    hide_send_mail: ".o-mail-Chatter-sendMessage",
    hide_log_notes: ".o-mail-Chatter-logNote",
    hide_schedule_activity: ".o-mail-Chatter-activity",
};

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.velkioChatterOrm = useService("orm");
        this.velkioChatterRootRef = useRef("compiled_view_root");
        this.velkioHiddenChatterButtons = [];
        this.velkioChatterObserver = null;

        onWillStart(async () => {
            const model = this.props.record?.resModel;
            if (!model) {
                return;
            }
            const res = await this.velkioChatterOrm.call(
                "access.management",
                "get_chatter_hide_details",
                [user.userId, false, model]
            );
            this.velkioHiddenChatterButtons = Object.entries(BTN_SELECTORS)
                .filter(([key]) => !res[key])
                .map(([, selector]) => selector);
        });

        useEffect(
            (el) => {
                if (!el || !this.velkioHiddenChatterButtons.length) {
                    return;
                }
                const apply = () => {
                    for (const selector of this.velkioHiddenChatterButtons) {
                        el.querySelectorAll(selector).forEach((btn) => {
                            btn.style.display = "none";
                        });
                    }
                };
                apply();
                this.velkioChatterObserver = new MutationObserver(apply);
                this.velkioChatterObserver.observe(el, { childList: true, subtree: true });
                return () => {
                    this.velkioChatterObserver?.disconnect();
                    this.velkioChatterObserver = null;
                };
            },
            () => [this.velkioChatterRootRef.el]
        );

        onWillUnmount(() => this.velkioChatterObserver?.disconnect());
    },
});
