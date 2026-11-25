# -*- coding: utf-8 -*-
from odoo import models, fields

# Preferences a person may read and change on their own account.
ZENVIO_SELF_FIELDS = [
    'zenvio_popup_enabled',
    'zenvio_sound_enabled',
    'zenvio_desktop_enabled',
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    zenvio_popup_enabled = fields.Boolean(
        string='Show Notification Popups', default=True,
        help='Turn this off to stop popups appearing on your screen. '
             'Urgent notifications are still shown.'
    )
    zenvio_sound_enabled = fields.Boolean(
        string='Play a Sound', default=True,
        help='A short chime when a notification appears.'
    )
    zenvio_desktop_enabled = fields.Boolean(
        string='Also Show in the System Notifications', default=True,
        help='Shows the same reminder in your operating system notification '
             'area, so you see it even when Odoo is not the window in front. '
             'Your browser will ask permission the first time.'
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ZENVIO_SELF_FIELDS

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ZENVIO_SELF_FIELDS
