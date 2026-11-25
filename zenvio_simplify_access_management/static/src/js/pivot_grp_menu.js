/** @odoo-module **/

import { PivotHeader } from "@web/views/pivot/pivot_header";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

/**
 * Odoo 18 replaced ``PivotGroupByMenu`` with ``PivotHeader`` (the in-table
 * "Group by" / "Add Custom Group" dropdown). Drop the fields hidden by an
 * Access-Studio "Field Access -> Invisible" rule from its field list.
 */
patch(PivotHeader.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        onWillStart(async () => {
            const resModel = this.env.searchModel?.resModel;
            if (!resModel) {
                return;
            }
            const hidden = await this.orm.call("access.management", "get_hidden_field", [
                "",
                resModel,
            ]);
            if (hidden && hidden.length) {
                this.fields = this.fields.filter((f) => !hidden.includes(f.name));
            }
        });
    },
});
