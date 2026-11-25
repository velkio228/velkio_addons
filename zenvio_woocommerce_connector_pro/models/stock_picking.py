from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        orders = self.filtered(lambda p: p.picking_type_code == "outgoing").sale_id
        orders.filtered(lambda o: o.delivery_status == "full")._woo_push_status("completed")
        return res
