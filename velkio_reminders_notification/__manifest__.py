# -*- coding: utf-8 -*-
{
    'name': 'Velkio Reminders & Notifications',
    'version': '17.0.1.1.0',
    'category': 'Productivity',
    'summary': 'On-screen reminders & notifications for Odoo — instant popups, '
               'snooze, dashboard, calendar & 39 ready templates',
    'description': """
Velkio Reminders & Notifications — On-Screen Popups & Alerts for Odoo
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
    'author': 'Velkio',
    'maintainer': 'Velkio',
    'website': 'https://velkio.com',
    'support': 'velkio.odoosolution@gmail.com',
    'license': 'LGPL-3',
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
        'security/velkio_security.xml',
        'security/ir.model.access.csv',
        'data/velkio_cron.xml',
        'data/velkio_template_data.xml',
        'views/velkio_notification_views.xml',
        'views/velkio_config_views.xml',
        'views/res_users_views.xml',
        'views/velkio_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'velkio_reminders_notification/static/src/scss/velkio_popup.scss',
            'velkio_reminders_notification/static/src/scss/velkio_dashboard.scss',
            'velkio_reminders_notification/static/src/scss/velkio_backend.scss',
            'velkio_reminders_notification/static/src/js/velkio_sound.js',
            'velkio_reminders_notification/static/src/js/velkio_service.js',
            'velkio_reminders_notification/static/src/js/velkio_popup.js',
            'velkio_reminders_notification/static/src/js/velkio_systray.js',
            'velkio_reminders_notification/static/src/js/velkio_read_eye.js',
            'velkio_reminders_notification/static/src/js/velkio_dashboard.js',
            'velkio_reminders_notification/static/src/xml/velkio_popup.xml',
            'velkio_reminders_notification/static/src/xml/velkio_systray.xml',
            'velkio_reminders_notification/static/src/xml/velkio_read_eye.xml',
            'velkio_reminders_notification/static/src/xml/velkio_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
