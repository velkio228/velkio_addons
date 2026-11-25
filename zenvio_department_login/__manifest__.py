{
    'name': 'Zenvio Department Access',
    'version': '19.0.8.3.0',
    'summary': 'Department & role access control, one-click Switch User and secure employee code login.',
    'description': """
Zenvio Department Access
========================

Give every department, role and employee exactly the access they need.

* **Department access**: User and Manager rules per department, personal
  access for a single employee.
* **Eight rule types**: menus, models, fields, records, buttons and tabs,
  filters, chatter, and global switches (read-only, import / export,
  developer mode, disable login).
* **Switch User**: open Odoo as any employee in one click, and come back.
* **Employee code login**: secure sign-in for shared terminals, with every
  login and switch logged.

Odoo Enterprise: every person working in Odoo must be covered by your Odoo
subscription.
""",
    'category': 'Productivity',
    'author': 'Zenvio - Odoo Solutions',
    'maintainer': 'Zenvio - Odoo Solutions',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Zenvio%20-%20Odoo%20Solutions',
    'support': 'zenvio.odoosolution@gmail.com',
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
    'depends': ['hr', 'mail', 'web'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/access_profile_views.xml',
        'views/department_access_views.xml',
        'views/department_login_log_views.xml',
        'views/res_users_views.xml',
        'views/login_templates.xml',
        'views/menu_views.xml',
        'wizard/department_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'zenvio_department_login/static/src/scss/department_login.scss',
            'zenvio_department_login/static/src/js/department_systray.js',
            'zenvio_department_login/static/src/js/department_fields.js',
            'zenvio_department_login/static/src/xml/department_fields.xml',
            'zenvio_department_login/static/src/xml/department_systray.xml',
        ],
        'web.assets_web_dark': [
            'zenvio_department_login/static/src/scss/department_login.dark.scss',
        ],
    },
    'application': True,
    'installable': True,
}
