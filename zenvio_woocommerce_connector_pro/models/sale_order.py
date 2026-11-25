import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# WooCommerce statuses an Odoo event may move an order away from. Orders that
# are already further along (or closed) in WooCommerce are left alone.
STATUS_ALLOWED_FROM = {
    "processing": {"pending", "on-hold"},
    "completed": {"pending", "on-hold", "processing"},
    "cancelled": {"pending", "on-hold", "processing"},
}


class WooSaleOrderMapping(models.Model):
    _inherit = "woo.sale.order.mapping"

    def _push_status(self, status):
        for mapping in self:
            if mapping.woo_status not in STATUS_ALLOWED_FROM[status]:
                continue
            instance = mapping.instance_id
            try:
                instance._woo_request("PUT", f"orders/{mapping.woo_id}", payload={"status": status})
            except UserError as error:
                # Never block the Odoo workflow because the store is unreachable.
                instance._create_log("push_status", state="failed", message=_(
                    "Order %(number)s -> %(status)s: %(error)s",
                    number=mapping.woo_order_number or mapping.woo_id, status=status, error=error,
                ))
                continue
            mapping.write({"woo_status": status, "last_sync_date": fields.Datetime.now()})


class SaleOrder(models.Model):
    _inherit = "sale.order"

    woo_mapping_ids = fields.One2many("woo.sale.order.mapping", "sale_order_id")
    woo_status = fields.Char(string="WooCommerce Status", compute="_compute_woo_status")

    def _compute_woo_status(self):
        for order in self:
            order.woo_status = order.woo_mapping_ids[:1].woo_status

    def _woo_push_status(self, status):
        if self.env.context.get("woo_skip_status_push"):
            return
        mappings = self.env["woo.sale.order.mapping"].sudo().search([
            ("sale_order_id", "in", self.ids),
            ("instance_id.push_order_status", "=", True),
        ])
        mappings._push_status(status)

    def _action_confirm(self):
        res = super()._action_confirm()
        self._woo_push_status("processing")
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        self._woo_push_status("cancelled")
        return res
