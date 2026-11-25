from odoo import fields, models


class WooSyncLog(models.Model):
    _inherit = "woo.sync.log"

    operation = fields.Selection(
        selection_add=[
            ("auto_sync", "Automatic Sync"),
            ("export_stock", "Export Stock"),
            ("webhook", "Webhook"),
            ("register_webhooks", "Register Webhooks"),
            ("push_status", "Push Order Status"),
            ("import_taxes", "Import Tax Rates"),
        ],
        ondelete={
            "auto_sync": "cascade",
            "export_stock": "cascade",
            "webhook": "cascade",
            "register_webhooks": "cascade",
            "push_status": "cascade",
            "import_taxes": "cascade",
        },
    )
