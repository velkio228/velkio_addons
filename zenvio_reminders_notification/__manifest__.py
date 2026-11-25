# -*- coding: utf-8 -*-
{
    'name': 'Zenvio Reminders & Notifications',
    'version': '17.0.1.1.0',
    'category': 'Productivity',
    'summary': 'On-screen reminders & notifications for Odoo — instant popups, '
               'snooze, dashboard, calendar & 39 ready templates',
    'description': """
Zenvio Reminders & Notifications — On-Screen Popups & Alerts for Odoo
=======================================================================

A small, focused tool for two everyday needs:

* **Tell someone something now** — an informational notice that appears on
  their screen wherever they are working.
* **Remind yourself later** — set a note for a time, and it pops up when the
  moment arrives.

How it behaves
--------------
* The popup appears over whatever screen the user is on. It never blocks the
  page: work continues behind it until the user answers.
* The same account open on several devices sees the notice on all of them, and
  answering on one takes it down on the rest.
* A device that was closed or asleep still gets the notice the moment it opens.
* Optional acknowledgement, snooze, auto-close countdown and a short sound.

Highlights
----------
* 6 ready-made popup designs and 39 ready-made message templates.
* A live dashboard, a personal calendar and read-tracking with an unread badge.
* Installs in minutes, no configuration required — free & open source (LGPL-3).
* Backed by 123 automated tests, including multi-device / multi-session cases.

Everyone can create reminders for themselves. Sending to other people, or to
everybody, is reserved for the Notification Manager group.

Keywords
--------
odoo reminders, odoo notifications, screen popup odoo, on-screen alert,
desktop notification odoo, task reminder odoo, meeting reminder, popup
reminder, notification popup odoo 17, broadcast message odoo, employee
reminder, notification dashboard, reminder calendar, notification templates,
alert popup, snooze reminder, acknowledge notification, multi device
notification, system tray notification odoo, bell notification odoo.
""",
    'author': 'Zenvio - Odoo Solutions',
    'maintainer': 'Zenvio - Odoo Solutions',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Zenvio%20-%20Odoo%20Solutions',
    'support': 'zenvio.odoosolution@gmail.com',
    'license': 'LGPL-3',
    'price': 29.0,
    'currency': 'USD',
    'images': [
        'static/description/banner.png',
        'static/description/01_dashboard.jpg',
        'static/description/07_popup_stack.jpg',
        'static/description/icon.png',
    ],
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/zenvio_security.xml',
        'security/ir.model.access.csv',
        'data/zenvio_cron.xml',
        'data/zenvio_template_data.xml',
        'views/zenvio_notification_views.xml',
        'views/zenvio_config_views.xml',
        'views/res_users_views.xml',
        'views/zenvio_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'zenvio_reminders_notification/static/src/scss/zenvio_popup.scss',
            'zenvio_reminders_notification/static/src/scss/zenvio_dashboard.scss',
            'zenvio_reminders_notification/static/src/scss/zenvio_backend.scss',
            'zenvio_reminders_notification/static/src/js/zenvio_sound.js',
            'zenvio_reminders_notification/static/src/js/zenvio_service.js',
            'zenvio_reminders_notification/static/src/js/zenvio_popup.js',
            'zenvio_reminders_notification/static/src/js/zenvio_systray.js',
            'zenvio_reminders_notification/static/src/js/zenvio_read_eye.js',
            'zenvio_reminders_notification/static/src/js/zenvio_dashboard.js',
            'zenvio_reminders_notification/static/src/xml/zenvio_popup.xml',
            'zenvio_reminders_notification/static/src/xml/zenvio_systray.xml',
            'zenvio_reminders_notification/static/src/xml/zenvio_read_eye.xml',
            'zenvio_reminders_notification/static/src/xml/zenvio_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
