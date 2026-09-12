# -*- coding: utf-8 -*-
from odoo import models, fields

# Preferences a person may read and change on their own account.
VELKIO_SELF_FIELDS = [
    'velkio_popup_enabled',
    'velkio_sound_enabled',
    'velkio_desktop_enabled',
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    velkio_popup_enabled = fields.Boolean(
        string='Show Notification Popups', default=True,
        help='Turn this off to stop popups appearing on your screen. '
             'Urgent notifications are still shown.'
    )
    velkio_sound_enabled = fields.Boolean(
        string='Play a Sound', default=True,
        help='A short chime when a notification appears.'
    )
    velkio_desktop_enabled = fields.Boolean(
        string='Also Show in the System Notifications', default=True,
        help='Shows the same reminder in your operating system notification '
             'area, so you see it even when Odoo is not the window in front. '
             'Your browser will ask permission the first time.'
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + VELKIO_SELF_FIELDS

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + VELKIO_SELF_FIELDS
