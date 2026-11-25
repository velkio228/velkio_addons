# -*- coding: utf-8 -*-
#############################################################################
#  Author      : Zenvio - Odoo Solutions  (https://apps.odoo.com)
#  Copyright(c): 2021-2026 - All Rights Reserved.
#
#  This module and its source code are the copyright property of the author
#  mentioned above. You may not redistribute, resell, sub-license or recreate
#  it, in whole or in part, for any purpose.
#############################################################################
{
    'name': 'Zenvio Simplify Access Management',
    'version': '17.0.6.1.0',
    'category': 'Tools',
    'sequence': 5,
    'summary': 'Control menus, fields, views, buttons, tabs, reports, filters and '
               'record rights per user from one screen - no record rules, no XML.',

    'description': """
Simplify Access Management
==========================

Setting up access rights in Odoo means juggling groups, record rules, view
overrides and menu visibility. This app replaces all of that with a single,
user-friendly record - the **Access Studio** - where you define exactly what a
group of users may see and do.

What you can control
--------------------
* **Hide Menu** - hide any application menu or sub-menu (parent hides its children).
* **Model Access** - per model, hide reports, server actions, whole view types
  (List, Kanban, Pivot, Graph, Calendar, Activity...) and the Create, Edit,
  Delete, Archive, Duplicate, Import, Export and Insert-in-Spreadsheet buttons.
* **Field Access** - make any field invisible, read-only or required, and remove
  the "open record" link on relational fields.
* **Domain Access** - real, enforced rights: allow/block Read, Create, Update and
  Delete, and optionally restrict the visible records with a filter. Applies
  everywhere - interface, imports, automated actions, API and Point of Sale.
* **Button / Tab Access** - hide individual action & object buttons (incl. smart
  buttons), form notebook tabs and Kanban action links.
* **Hide Filter / Group By** - remove specific search-panel filters and group-by
  options of a model.
* **Chatter** - hide the chatter per model, or just its Send Message / Log Note /
  Schedule Activity buttons.
* **Global** - apply a rule to every model at once: hide chatter, hide Import &
  Export, disable login, force developer mode off, or **disable Create / Edit on
  every relational field** so users can only pick from existing records.

Every rule is user- and company-aware, can be activated or deactivated without
being deleted, and each tab carries built-in guidance so administrators do not
need a manual. Multi-company is fully supported.

The advanced domain / record-picker widget is now **bundled inside this module**
- no separate dependency to install.

Keywords
--------
access management, access rights manager, user access rights, hide menu,
hide field, hide button, hide report, hide view, read-only user, restrict
create/edit/delete, record rules alternative, field access, model access,
menu access, domain access, chatter access, hide filters, hide group by,
multi company access, Odoo 17 security.
    """,

    'author': 'Zenvio - Odoo Solutions',
    'maintainer': 'Zenvio - Odoo Solutions',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Zenvio%20-%20Odoo%20Solutions',
    'support': 'zenvio.odoosolution@gmail.com',
    'license': 'OPL-1',
    'price': 45.0,
    'currency': 'USD',

    'images': [
        'static/description/banner.png',
        'static/description/screenshot_list.png',
        'static/description/screenshot_form.png',
        'static/description/icon.png',
    ],

    'depends': [
        'web',
    ],

    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/view_data.xml',
        'views/access_management_view.xml',
        'views/res_users_view.xml',
        'views/store_model_nodes_view.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # ---- Access Management behaviour & theme ----
            'zenvio_simplify_access_management/static/src/js/action_menus.js',
            'zenvio_simplify_access_management/static/src/js/hide_chatter.js',
            'zenvio_simplify_access_management/static/src/js/cog_menu.js',
            'zenvio_simplify_access_management/static/src/js/form_controller.js',
            'zenvio_simplify_access_management/static/src/js/pivot_grp_menu.js',
            'zenvio_simplify_access_management/static/src/js/model_field_selector.js',
            'zenvio_simplify_access_management/static/src/xml/studio_dialog.xml',
            'zenvio_simplify_access_management/static/src/scss/zenvio_theme.scss',
            # ---- Advanced domain widget (merged; provides the "zenvio_domain" field) ----
            'zenvio_simplify_access_management/static/src/core/**/*',
            'zenvio_simplify_access_management/static/src/dateSelectionBits/dateSelectionBits.js',
            'zenvio_simplify_access_management/static/src/dateSelectionBits/dateSelectionBits.xml',
            'zenvio_simplify_access_management/static/src/fields/domain/domain_field.js',
            'zenvio_simplify_access_management/static/src/fields/domain/domain_field.xml',
        ],
    },

    'post_init_hook': 'post_install_action_dup_hook',

    'application': True,
    'installable': True,
    'auto_install': False,
    'live_test_url': 'https://apps.odoo.com/apps/modules/browse?author=Zenvio%20-%20Odoo%20Solutions',
}
