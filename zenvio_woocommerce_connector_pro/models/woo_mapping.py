from odoo import fields, models


class WooProductMapping(models.Model):
    _inherit = "woo.product.mapping"

    image_src = fields.Char(string="Image URL", readonly=True)
    woo_stock_qty = fields.Float(string="Last Pushed Stock", readonly=True)


class WooVariantMapping(models.Model):
    _name = "woo.variant.mapping"
    _description = "WooCommerce Variation Mapping"
    _rec_name = "product_id"

    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade", index=True)
    woo_id = fields.Char(required=True, string="WooCommerce Variation ID")
    woo_parent_id = fields.Char(required=True, string="WooCommerce Product ID")
    sku = fields.Char()
    product_id = fields.Many2one("product.product", required=True, ondelete="cascade")
    woo_stock_qty = fields.Float(string="Last Pushed Stock", readonly=True)
    last_sync_date = fields.Datetime()

    _woo_variant_unique = models.Constraint(
        "unique(instance_id, woo_id)",
        "This WooCommerce variation is already mapped for this instance.",
    )


class WooTaxMapping(models.Model):
    _name = "woo.tax.mapping"
    _description = "WooCommerce Tax Rate Mapping"
    _order = "instance_id, name"

    instance_id = fields.Many2one("woo.instance", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="instance_id.company_id")
    woo_id = fields.Char(required=True, string="WooCommerce Rate ID")
    name = fields.Char(required=True)
    rate = fields.Float(digits=(16, 4))
    tax_id = fields.Many2one(
        "account.tax",
        string="Odoo Tax",
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]",
        help="WooCommerce line amounts exclude tax, so map to a tax that is not included in price.",
    )

    _woo_tax_unique = models.Constraint(
        "unique(instance_id, woo_id)",
        "This WooCommerce tax rate is already mapped for this instance.",
    )
