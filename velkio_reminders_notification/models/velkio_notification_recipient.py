# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Delivered and still open one way or another. The bell no longer counts these
# — it counts anything unread — but a notice in one of them has not been
# answered, so it still belongs to the reader.
OPEN_STATES = ('sent', 'seen')


class VelkioNotificationRecipient(models.Model):
    """One row per person per notification: what they were sent and what they did."""

    _name = 'velkio.notification.recipient'
    _description = 'Screen Notification Recipient'
    _order = 'sent_at desc, id desc'
    _rec_name = 'notification_id'

    notification_id = fields.Many2one(
        'velkio.notification', string='Notification',
        required=True, ondelete='cascade', index=True
    )
    user_id = fields.Many2one(
        'res.users', string='Person', required=True, ondelete='cascade', index=True
    )
    partner_id = fields.Many2one('res.partner', string='Contact')
    state = fields.Selection([
        ('sent', 'On screen'),
        ('seen', 'Seen'),
        ('done', 'Answered'),
        ('snoozed', 'Snoozed'),
        ('muted', 'Muted by the reader'),
    ], string='Status', default='sent', required=True, index=True)

    sent_at = fields.Datetime(string='Sent At')
    seen_at = fields.Datetime(string='Seen At')
    done_at = fields.Datetime(string='Answered At')
    snooze_until = fields.Datetime(string='Snoozed Until', index=True)
    snooze_count = fields.Integer(string='Snoozes', default=0)
    acknowledged = fields.Boolean(
        string='Acknowledged',
        help='Ticked when the reader clicked the acknowledgement button.'
    )
    dismissed_at = fields.Datetime(
        string='Cleared From Screen', index=True,
        help='Set when the reader used "Close all". Seen means some device '
             'displayed it; dismissed means the reader deliberately cleared '
             'it, and only that stops the other devices showing it.'
    )
    read_at = fields.Datetime(
        string='Read At', index=True,
        help='When this person actually read the notice — either by answering '
             'the popup or by opening it from their list. Anything unread is '
             'what the bell counts.'
    )

    _sql_constraints = [
        ('user_notification_uniq',
         'unique(notification_id, user_id)',
         'A person can only be on a notification once.'),
    ]

    def write(self, vals):
        """Closing a row also reads it.

        The bell counts unread rows, and several paths close one: answering
        the popup, the Mark Done button on the list, and a snooze waking on a
        notice that has since been cancelled. Stamping here rather than in
        each of them means a finished notice can never be left sitting in
        somebody's count with no way to clear it.
        """
        if vals.get('state') == 'done' and 'read_at' not in vals:
            vals = dict(vals, read_at=fields.Datetime.now())
        # Going back on screen — a snooze running out, or a deliberate
        # re-send — undoes an earlier clearing.
        if vals.get('state') == 'sent' and 'dismissed_at' not in vals:
            vals = dict(vals, dismissed_at=False)
        return super().write(vals)

    @api.model
    def _unread_count(self, user=None):
        """How many notices this reader still has to read.

        The bell shows this. Muted rows are included on purpose: switching
        popups off means "do not interrupt me", not "hide it from my list".
        """
        user = user or self.env.user
        return self.sudo().search_count([
            ('user_id', '=', user.id),
            ('read_at', '=', False),
        ])

    def _mark_read(self):
        """Stamp these rows as read and tell the reader's other devices."""
        unread = self.sudo().filtered(lambda r: not r.read_at)
        if not unread:
            return
        unread.write({'read_at': fields.Datetime.now()})
        for user in unread.mapped('user_id'):
            try:
                self.env['bus.bus']._sendone(
                    user.partner_id, 'velkio_notification_count',
                    {'count': self._unread_count(user)},
                )
            except Exception:
                _logger.exception('Could not broadcast the unread count.')

    def action_mark_done(self):
        """Close these notifications.

        The table is read-only for ordinary people, so the write is done with
        sudo after checking that the row really is theirs. Without that, a
        person could not even dismiss a notice addressed to them.
        """
        manager = 'velkio_reminders_notification.group_velkio_manager'
        for row in self:
            if self.env.su or self.env.user.has_group(manager):
                continue
            if row.user_id != self.env.user:
                raise AccessError(_('You can only close your own notifications.'))
        self.sudo().write({'state': 'done', 'done_at': fields.Datetime.now()})

    @api.model
    def _cron_wake_snoozed(self):
        """Show snoozed notifications again once their time is up."""
        now = fields.Datetime.now()
        rows = self.sudo().search([
            ('state', '=', 'snoozed'),
            ('snooze_until', '!=', False),
            ('snooze_until', '<=', now),
        ])
        for row in rows:
            try:
                if row.notification_id._resend_to_user(row.user_id):
                    row.write({'state': 'sent', 'sent_at': now})
                else:
                    row.write({'state': 'done', 'done_at': now})
            except Exception:
                _logger.exception('Could not wake snoozed notification %s', row.id)
