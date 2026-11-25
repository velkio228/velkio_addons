{
    "name": "Zenvio WooCommerce Connector Pro",
    "version": "19.0.1.0.0",
    "category": "Sales/eCommerce",
    "summary": "Automatic WooCommerce sync: stock, variants, webhooks, order status, shipping and taxes",
    "description": """
WooCommerce Connector Pro
=========================

Extends Zenvio WooCommerce Connector with scheduled incremental sync, real-time
webhooks, stock push from Odoo, product variations and images, shipping and fee
lines, tax-rate mapping, delivery addresses and two-way order status updates.
    """,
    "author": "Zenvio - Odoo Solutions",
    "maintainer": "Zenvio - Odoo Solutions",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Zenvio%20-%20Odoo%20Solutions",
    "support": "zenvio.odoosolution@gmail.com",
    "license": "OPL-1",
    "price": 39.0,
    "currency": "USD",
    "depends": ["zenvio_woocommerce_connector", "sale_stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/product_data.xml",
        "data/ir_cron.xml",
        "views/woo_mapping_views.xml",
        "views/woo_instance_views.xml",
        "views/sale_order_views.xml",
        "views/woo_menus.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
