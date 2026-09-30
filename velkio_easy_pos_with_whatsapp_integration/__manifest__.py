# -*- coding: utf-8 -*-
{'name': 'Velkio Easy POS with WhatsApp Integration',
 'version': '17.0.1.0.0',
 'category': 'Sales',
 'summary': 'Counter billing, stock delivery and WhatsApp PDF receipts in one app',
 'description': 'Velkio Easy POS with WhatsApp Integration\n'
                '===========================================\n'
                'Standalone counter billing with product search, parked bills, pricelists, '
                'tax\n'
                'breakdown, stock delivery, PDF receipts and queued WhatsApp receipt '
                'messages.\n'
                'Requires Odoo 17 Enterprise WhatsApp, a configured business account and an\n'
                'approved document template. Payment methods record the tender choice; this\n'
                'module does not charge cards or create accounting payments/invoices.\n',
 'author': 'Velkio',
 'company': 'Velkio',
 'maintainer': 'Velkio',
 'website': 'https://velkio.com',
 'depends': ['base', 'web', 'mail', 'product', 'stock', 'account', 'whatsapp'],
 'data': ['security/pos_screen_security.xml',
          'security/ir.model.access.csv',
          'data/pos_screen_sequence.xml',
          'data/pos_screen_data.xml',
          'views/pos_screen_config_views.xml',
          'views/pos_screen_order_views.xml',
          'views/pos_screen_inventory_views.xml',
          'views/pos_screen_menus.xml',
          'report/pos_screen_receipt_template.xml',
          'report/pos_screen_report.xml',
          'data/whatsapp_template_data.xml',
          'views/whatsapp_pos_screen_config_views.xml',
          'views/whatsapp_pos_screen_order_views.xml'],
 'assets': {'web.assets_backend': ['velkio_easy_pos_with_whatsapp_integration/static/src/scss/pos_screen.scss',
                                   'velkio_easy_pos_with_whatsapp_integration/static/src/js/pos_screen.js',
                                   'velkio_easy_pos_with_whatsapp_integration/static/src/xml/pos_screen.xml']},
 'installable': True,
 'auto_install': False,
 'application': True,
 'license': 'LGPL-3',
 'support': 'velkio.odoosolution@gmail.com',
 'images': ['static/description/banner.png'],
 'pre_init_hook': 'pre_init_hook'}
