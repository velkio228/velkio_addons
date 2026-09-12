# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

# Delivered and still unanswered. A device replays these when it opens, so a
# notice that fired while it was closed is not missed — and so the same account
# on a second screen still gets it after the first screen has displayed it.
OPEN_STATES = ('sent', 'seen')

# A device that has been away for a while should not be buried under a backlog.
CATCHUP_LIMIT = 5
CATCHUP_MAX_AGE_DAYS = 7

# How far ahead the browser is told about, so it can arm its own timer and
# show the popup on the exact second it falls due.
PREFETCH_MINUTES = 15


class VelkioNotificationController(http.Controller):

    # ── helpers ───────────────────────────────────────────────────

    def _own_row(self, notification_id, create=False):
        """This user's recipient row.

        Read with sudo: people are not given write access to the table, they
        may only change their own row through these endpoints.

        With `create`, the row is made if it is missing. The browser can show a
        notice the instant it falls due, a moment before the cron has written
        anything, and the reader must still be able to answer it.
        """
        try:
            notification_id = int(notification_id)
        except (TypeError, ValueError):
            return request.env['velkio.notification.recipient'].sudo().browse()
        user = request.env.user
        Recipient = request.env['velkio.notification.recipient'].sudo()
        row = Recipient.search([
            ('notification_id', '=', notification_id),
            ('user_id', '=', user.id),
        ], limit=1)
        if row or not create:
            return row
        notification = request.env['velkio.notification'].sudo().browse(notification_id)
        if not notification.exists() or not notification.is_due_for(user):
            return Recipient.browse()
        return Recipient.create({
            'notification_id': notification.id,
            'user_id': user.id,
            'partner_id': user.partner_id.id,
            'state': 'sent',
            'sent_at': fields.Datetime.now(),
        })

    def _open_count(self):
        """What the bell shows: everything this reader has not read yet."""
        return request.env['velkio.notification.recipient']._unread_count()

    def _close_on_other_devices(self, row):
        try:
            row.notification_id._notify_closed(request.env.user)
        except Exception:
            _logger.exception('Could not broadcast close for recipient %s', row.id)

    # ── what the browser asks for ─────────────────────────────────

    @http.route('/velkio/notification/pending', type='json', auth='user')
    def pending(self, **kwargs):
        """Everything still waiting for this person.

        Bus messages are dropped after about a hundred seconds, so a browser
        that was closed, asleep or simply reloaded would otherwise never see a
        notification that fired while it was away. This hands them back.
        """
        user = request.env.user
        rows = request.env['velkio.notification.recipient'].sudo().search([
            # Still unanswered, and not deliberately cleared off the screen.
            # "Seen" only means some device displayed it, which must not stop
            # the same person's other screens from showing it too.
            '|',
            '&', ('state', 'in', OPEN_STATES),
                 ('dismissed_at', '=', False),
            # One that must be acknowledged comes back regardless.
            '&', ('state', 'in', OPEN_STATES),
                 ('notification_id.require_ack', '=', True),
            ('user_id', '=', user.id),
            ('sent_at', '>=', fields.Datetime.now() - timedelta(days=CATCHUP_MAX_AGE_DAYS)),
            ('notification_id.state', '=', 'sent'),
        ], order='id desc', limit=CATCHUP_LIMIT)

        popups = []
        for row in rows:
            try:
                popups.append(row.notification_id._payload(user))
            except Exception:
                _logger.exception('Could not rebuild payload for recipient %s', row.id)
        popups.reverse()  # oldest first, so the newest ends up on top
        return {
            'popups': popups,
            'upcoming': self._upcoming_for(user),
            'count': self._open_count(),
        }

    def _upcoming_for(self, user):
        """Notices about to fall due, with how long is left on each.

        The browser arms its own timer from this, which is what makes a popup
        land on the exact second rather than whenever the cron next ticks. The
        delay is sent as a duration, not a wall-clock time, so a browser whose
        clock is off is not affected.
        """
        now = fields.Datetime.now()
        soon = now + timedelta(minutes=PREFETCH_MINUTES)
        candidates = request.env['velkio.notification'].sudo().search([
            ('state', '=', 'scheduled'),
            ('notify_datetime', '>', now),
            ('notify_datetime', '<=', soon),
        ], limit=50)

        upcoming = []
        for notification in candidates:
            if user not in notification._get_audience():
                continue
            delay = (notification.notify_datetime - now).total_seconds()
            upcoming.append({
                'id': notification.id,
                'delay_ms': max(0, int(delay * 1000)),
            })
        return upcoming

    @http.route('/velkio/notification/fire', type='json', auth='user', methods=['POST'])
    def fire(self, notification_id, **kwargs):
        """The browser's timer went off: check it is really due, then show it.

        The server stays the authority. A notice that was cancelled, moved or
        already answered in the meantime is refused here, so an armed timer can
        never put a stale popup on screen.
        """
        user = request.env.user
        notification = request.env['velkio.notification'].sudo().browse(
            int(notification_id) if str(notification_id).isdigit() else 0
        )
        if not notification.exists() or not notification.is_due_for(user):
            return {'ok': False}
        row = self._own_row(notification.id, create=True)
        if not row or row.state in ('done', 'snoozed', 'muted'):
            return {'ok': False}
        return {
            'ok': True,
            'popup': notification._payload(user),
            'count': self._open_count(),
        }

    @http.route('/velkio/notification/seen', type='json', auth='user', methods=['POST'])
    def mark_seen(self, notification_id, **kwargs):
        row = self._own_row(notification_id, create=True)
        if row and row.state == 'sent':
            row.write({'state': 'seen', 'seen_at': fields.Datetime.now()})
        return {'success': True}

    @http.route('/velkio/notification/done', type='json', auth='user', methods=['POST'])
    def mark_done(self, notification_id, acknowledged=False, **kwargs):
        """Closed or acknowledged: either way the reader is finished with it."""
        row = self._own_row(notification_id, create=True)
        if not row:
            return {'success': False, 'error': 'Not found'}
        row.write({
            'state': 'done',
            'done_at': fields.Datetime.now(),
            'acknowledged': bool(acknowledged),
        })
        # Closing the row stamps it read (see the model's write), and the
        # take-down message carries the new count to the other devices.
        self._close_on_other_devices(row)
        return {'success': True, 'count': self._open_count()}

    @http.route('/velkio/notification/dismiss_all', type='json', auth='user',
                methods=['POST'])
    def dismiss_all(self, **kwargs):
        """Take every popup off the screen without reading any of them.

        This clears the view, nothing more. The notices stay unread, so they
        keep their place in the bell and in the list until they are actually
        opened. Marking them seen is what stops them popping straight back up
        on the next catch-up.

        Two kinds are left alone: snoozed ones, which were put off to a chosen
        time, and any that require an acknowledgement, whose whole purpose is
        to wait for an explicit answer.
        """
        rows = request.env['velkio.notification.recipient'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('state', 'in', OPEN_STATES),
            ('dismissed_at', '=', False),
            ('notification_id.require_ack', '=', False),
        ])
        if not rows:
            return {'success': True, 'dismissed': [], 'count': self._open_count()}

        now = fields.Datetime.now()
        rows.write({'dismissed_at': now})
        rows.filtered(lambda r: r.state == 'sent').write(
            {'state': 'seen', 'seen_at': now}
        )
        dismissed = rows.notification_id
        # One batch rather than a message per row: clearing a long backlog
        # should not put a hundred separate messages on the bus.
        dismissed._notify_closed_many(request.env.user)
        return {
            'success': True,
            'dismissed': dismissed.ids,
            'count': self._open_count(),
        }

    @http.route('/velkio/notification/snooze', type='json', auth='user', methods=['POST'])
    def snooze(self, notification_id, minutes=10, **kwargs):
        try:
            minutes = max(1, min(int(minutes), 24 * 60))
        except (TypeError, ValueError):
            minutes = 10
        row = self._own_row(notification_id, create=True)
        if not row:
            return {'success': False, 'error': 'Not found'}
        row.write({
            'state': 'snoozed',
            'snooze_until': fields.Datetime.now() + timedelta(minutes=minutes),
            'snooze_count': row.snooze_count + 1,
        })
        self._close_on_other_devices(row)
        return {'success': True, 'count': self._open_count()}
