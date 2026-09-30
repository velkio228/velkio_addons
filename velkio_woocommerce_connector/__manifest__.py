{
    "name": "Velkio WooCommerce Connector",
    "version": "19.0.1.0.1",
    "category": "Sales/eCommerce",
    "summary": "Connect WooCommerce with Odoo products, customers, and orders",
    "description": """
WooCommerce Connector
=====================

Import WooCommerce products, customers and new sales orders into Odoo. Export
mapped product names, SKUs and prices to the configured store. Includes multi-store
connections, manual actions, mappings, sync logs and an operational dashboard.
Requires a reachable WooCommerce store and REST API credentials. Customer and
order synchronization is inbound only. Imports read up to 1,000 records per resource.
    """,
    "author": "Velkio",
    "website": "https://apps.odoo.com/apps/modules/browse?author=Velkio%20-%20Odoo%20Solutions",
    "support": "velkio.odoosolution@gmail.com",
    "license": "OPL-1",
    'price': 1.0,
    'currency': 'USD',
    "depends": ["base", "sale_management", "stock", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/woo_mapping_views.xml",
        "views/woo_sync_log_views.xml",
        "views/woo_instance_views.xml",
        "views/woo_dashboard_views.xml",
        "views/woo_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "velkio_woocommerce_connector/static/src/js/woo_dashboard.js",
            "velkio_woocommerce_connector/static/src/xml/woo_dashboard.xml",
            "velkio_woocommerce_connector/static/src/scss/woo_dashboard.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/workflow.png",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}
