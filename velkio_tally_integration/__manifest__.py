# -*- coding: utf-8 -*-
{
    "name": "TallyPrime Connector",
    "summary": "Connect TallyPrime masters and transactions with configurable sync direction",
    "description": """
Velkio Odoo Tally Connector | TallyPrime Integration for Odoo 19
==========================================================
A native Odoo Tally connector for configurable, two-way synchronization between TallyPrime
and Odoo 19 Community or Enterprise on Odoo.sh and on-premise. Configure Tally-first, Odoo-first,
one-way or serialized bidirectional synchronization independently for every supported entity.

Supported master data includes groups, general accounts, parties, units of measure, stock groups,
stock items, godowns/locations, cost centres, taxes, and currencies. Supported transactions include
sales invoices, credit notes, purchase bills, debit notes, receipts, payments, journal/contra
vouchers, and internal stock transfers.

Configure Tally-first, Odoo-first, or bidirectional ownership with serialized processing and
SHA-256 echo suppression. The module includes a durable outbound queue, token-authenticated routes
for the optional on-premise agent, and native list, pivot, and graph monitoring views.
Requires a working TallyPrime installation with an accessible XML gateway.
Configured accounting, party, inventory and transaction data is exchanged with that
endpoint. Agent mode requires a separately deployed relay; no agent executable is bundled.
""",
    "version": "19.0.1.2.1",
    "category": "Accounting",
    "author": "Velkio – Odoo Solutions",
    "maintainer": "Velkio – Odoo Solutions",
    "website": "https://velkio.com",
    "support": "velkio.odoosolution@gmail.com",
    "license": "LGPL-3",
    "images": [
        "static/description/banner.png",
        "static/description/screenshots/01_dashboard.jpg",
        "static/description/screenshots/03_what_syncs.jpg",
        "static/description/screenshots/04_invoice_tally_post.jpg",
        "static/description/screenshots/07_outbound_queue.jpg",
        "static/description/workflow.png",
    ],
    "depends": ["base", "mail", "account", "uom", "product", "stock", "analytic"],
    "data": [
        "security/tally_security.xml",
        "security/ir.model.access.csv",
        "security/ir_rule_data.xml",
        "data/ir_cron_data.xml",
        "data/tally_account_type_map_data.xml",
        "views/tally_instance_views.xml",
        "views/tally_entity_config_views.xml",
        "views/tally_mapping_views.xml",
        "views/tally_sync_log_views.xml",
        "views/tally_sync_queue_views.xml",
        "views/tally_inbound_dead_letter_views.xml",
        "views/tally_account_type_map_views.xml",
        "views/tally_discovered_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/tally_push_buttons_views.xml",
        "wizard/tally_onboarding_views.xml",
        "views/tally_menus.xml",
        "views/tally_activity_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "velkio_tally_integration/static/src/scss/tally_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
