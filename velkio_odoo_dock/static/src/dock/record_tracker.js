/** @odoo-module **/

import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * Tell the dock which record is open, so it can list it under
 * "Recent Records" in the overview. Records opened in dialogs are ignored.
 */
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.env.inDialog) {
            return;
        }
        useEffect(
            (resId, name) => {
                if (resId && name) {
                    this.env.bus.trigger("VELKIO_DOCK:RECORD-OPENED", {
                        model: this.props.resModel,
                        id: resId,
                        name,
                    });
                }
            },
            () => [this.model.root.resId, this.displayName()]
        );
    },
});
