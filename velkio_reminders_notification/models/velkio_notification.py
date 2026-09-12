# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

import pytz

from odoo import models, fields, api, _
from odoo.tools import html2plaintext
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class VelkioNotification(models.Model):
    """A message that pops up on screen, either for other people or for yourself."""

    _name = 'velkio.notification'
    _description = 'Screen Notification'
    _order = 'notify_datetime desc, id desc'

    name = fields.Char(
        string='Title', required=True,
        help='Shown in bold at the top of the popup.'
    )
    body = fields.Html(
        string='Message', required=True, sanitize=True,
        help='What the popup says. Basic formatting and links are allowed.'
    )
    notify_datetime = fields.Datetime(
        string='Show At', required=True, index=True,
        default=lambda self: fields.Datetime.now() + timedelta(minutes=5),
        help='When the popup should appear. Entered in your own timezone.'
    )
    level = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Important'),
        ('urgent', 'Urgent'),
    ], string='Level', default='info', required=True,
        help='Sets the popup colour, and how insistent it is.')

    audience = fields.Selection([
        ('me', 'Only me'),
        ('users', 'Selected people'),
        ('all', 'Everyone'),
    ], string='Notify', default='me', required=True)
    user_ids = fields.Many2many(
        'res.users', 'velkio_notification_user_rel', 'notification_id', 'user_id',
        string='People', domain=[('share', '=', False)]
    )

    duration = fields.Integer(
        string='Auto-close After (seconds)', default=20,
        help='0 keeps the popup on screen until the reader closes it.'
    )
    require_ack = fields.Boolean(
        string='Require Acknowledgement',
        help='The reader must click Got it. The popup cannot be closed otherwise.'
    )
    allow_snooze = fields.Boolean(string='Allow Snooze', default=True)
    play_sound = fields.Boolean(string='Play Sound', default=True)
    # Flagging is personal. Everyone keeps their own stars, so one person
    # starring a company-wide notice does not flag it for the whole company.
    flag_user_ids = fields.Many2many(
        'res.users', 'velkio_notification_flag_rel', 'notification_id', 'user_id',
        string='Flagged By', copy=False
    )
    flagged = fields.Boolean(
        string='Flagged', compute='_compute_flagged', inverse='_inverse_flagged',
        search='_search_flagged',
        help='Star it to find it again from your dashboard. Only you see your stars.'
    )
    is_read = fields.Boolean(
        string='Read', compute='_compute_is_read', inverse='_inverse_is_read',
        search='_search_is_read',
        help='Whether you have read this one. Anything unread is what the bell '
             'counts. Only you see your own read marks.'
    )
    template_id = fields.Many2one(
        'velkio.template', string='Start From Template',
        help='Fills the notice in with ready-made wording.'
    )
    style_id = fields.Many2one(
        'velkio.popup.style', string='Popup Style',
        help='Leave empty to use the default style set in Configuration.'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, index=True, copy=False)
    sent_at = fields.Datetime(string='Sent At', readonly=True, copy=False)

    recipient_ids = fields.One2many(
        'velkio.notification.recipient', 'notification_id',
        string='Recipients', copy=False
    )
    recipient_count = fields.Integer(
        string='People Notified', compute='_compute_counts', store=True
    )
    open_count = fields.Integer(
        string='Waiting', compute='_compute_counts', store=True,
        help='People who have not answered yet.'
    )
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )
    can_edit = fields.Boolean(
        string='Can Edit', compute='_compute_can_edit',
        help='Only the person who wrote the notice can change it.'
    )

    # ── COMPUTE ───────────────────────────────────────────────────

    @api.depends_context('uid')
    @api.depends('flag_user_ids')
    def _compute_flagged(self):
        user = self.env.user
        # active_test=False: reading a many2many to res.users hides archived
        # accounts by default, which would make their own stars invisible.
        flagged_by = self.with_context(active_test=False)
        for record, unfiltered in zip(self, flagged_by):
            record.flagged = user in unfiltered.flag_user_ids

    def _inverse_flagged(self):
        """Starring adds only the current person to the list."""
        user = self.env.user
        for record in self:
            # sudo: a reader may star a notice they are not allowed to edit.
            if record.flagged:
                record.sudo().flag_user_ids = [(4, user.id)]
            else:
                record.sudo().flag_user_ids = [(3, user.id)]

    @api.depends_context('uid')
    @api.depends('recipient_ids.read_at')
    def _compute_is_read(self):
        """Read is per person: it lives on that reader's own delivery row.

        A notice nobody sent to this reader has no row, so there is nothing
        for them to have read; it reads as unread and simply never appears in
        their count.
        """
        rows = self._own_rows()
        for record in self:
            row = rows.get(record.id)
            record.is_read = bool(row and row.read_at)

    def _inverse_is_read(self):
        """Mark only the current reader's own row."""
        rows = self._own_rows()
        Recipient = self.env['velkio.notification.recipient']
        to_read, to_unread = Recipient, Recipient
        for record in self:
            row = rows.get(record.id)
            if not row:
                continue
            if record.is_read:
                to_read |= row
            else:
                to_unread |= row
        # sudo: the table is read-only for ordinary people, and this only ever
        # touches rows that belong to them.
        if to_read:
            to_read._mark_read()
        if to_unread:
            to_unread.sudo().write({'read_at': False})

    def _search_is_read(self, operator, value):
        """So "Unread" always means "unread by me"."""
        if operator not in ('=', '!='):
            raise ValueError(_('Unsupported search on Read.'))
        read = (operator == '=') == bool(value)
        mine = [('recipient_ids.user_id', '=', self.env.user.id)]
        if read:
            return mine + [('recipient_ids.read_at', '!=', False)]
        # Unread covers both "delivered but not read" and "never delivered".
        return ['|', ('recipient_ids.read_at', '=', False),
                ('id', 'not in', self._own_delivered_ids())]

    def _own_rows(self):
        """This reader's delivery row for each notice in self, keyed by id."""
        if not self:
            return {}
        rows = self.env['velkio.notification.recipient'].sudo().search([
            ('notification_id', 'in', self.ids),
            ('user_id', '=', self.env.user.id),
        ])
        return {row.notification_id.id: row for row in rows}

    def _own_delivered_ids(self):
        """Ids of notices actually delivered to this reader."""
        rows = self.env['velkio.notification.recipient'].sudo().search([
            ('user_id', '=', self.env.user.id),
        ])
        return rows.notification_id.ids

    def web_read(self, specification):
        """Opening one marks it read.

        The form asks for the message body and the list never does, so this
        fires when someone actually opens a notice rather than every time the
        list behind it refreshes.
        """
        result = super().web_read(specification)
        if 'body' in specification:
            try:
                self._mark_read()
            except Exception:
                _logger.exception('Could not mark notifications as read.')
        return result

    def _mark_read(self):
        """Stamp this reader's own delivery rows as read."""
        rows = self._own_rows()
        if not rows:
            return
        Recipient = self.env['velkio.notification.recipient']
        Recipient.browse([row.id for row in rows.values()])._mark_read()

    def action_toggle_read(self):
        """The eye in the list: read becomes unread and back again."""
        for record in self:
            record.is_read = not record.is_read
        return True

    def _search_flagged(self, operator, value):
        """So "Flagged" always means "flagged by me"."""
        if operator not in ('=', '!='):
            raise ValueError(_('Unsupported search on Flagged.'))
        starred = (operator == '=') == bool(value)
        if starred:
            return [('flag_user_ids', 'in', self.env.user.id)]
        return [('flag_user_ids', 'not in', self.env.user.id)]

    @api.depends_context('uid')
    @api.depends('create_uid')
    def _compute_can_edit(self):
        """Only the author changes a notice. Everyone else reads it."""
        user = self.env.user
        is_manager = user.has_group('velkio_reminders_notification.group_velkio_manager')
        for record in self:
            record.can_edit = (
                is_manager
                or not record.create_uid
                or record.create_uid.id == user.id
            )

    @api.depends('recipient_ids', 'recipient_ids.state')
    def _compute_counts(self):
        for record in self:
            recipients = record.recipient_ids
            record.recipient_count = len(recipients)
            record.open_count = len(
                recipients.filtered(lambda r: r.state in ('sent', 'seen', 'snoozed'))
            )

    # ── CONSTRAINTS ───────────────────────────────────────────────

    @api.constrains('audience', 'user_ids')
    def _check_audience(self):
        """Only a manager may put a popup on someone else's screen.

        This guards what a person does through the interface. Code running as
        superuser (the cron, sudo helpers, data files) is trusted and skipped,
        otherwise the system would not be able to send anything at all.
        """
        for record in self:
            if record.audience == 'users' and not record.user_ids:
                raise ValidationError(_('Please choose at least one person.'))
            if record.env.su:
                continue
            if record.env.user.has_group('velkio_reminders_notification.group_velkio_manager'):
                continue
            others = record.user_ids - record.env.user
            if record.audience == 'all' or (record.audience == 'users' and others):
                raise ValidationError(_(
                    'You can only send notifications to yourself. Ask a '
                    'Notification Manager to send one to other people.'
                ))

    @api.constrains('notify_datetime')
    def _check_notify_datetime(self):
        for record in self:
            if record.state == 'draft' and record.notify_datetime:
                if record.notify_datetime < datetime.utcnow() - timedelta(minutes=2):
                    raise ValidationError(_(
                        'That time has already passed. Pick a moment in the future.'
                    ))

    @api.constrains('duration')
    def _check_duration(self):
        for record in self:
            if record.duration < 0:
                raise ValidationError(_('Auto-close cannot be negative.'))

    # ── ONCHANGE ──────────────────────────────────────────────────

    @api.onchange('level')
    def _onchange_level(self):
        """Urgent notices stay on screen and ask for an answer."""
        if self.level == 'urgent':
            self.duration = 0
            self.require_ack = True
        elif self.level == 'warning':
            self.duration = 60

    @api.onchange('audience')
    def _onchange_audience(self):
        if self.audience != 'users':
            self.user_ids = [(5, 0, 0)]

    @api.onchange('template_id')
    def _onchange_template(self):
        """Fill the notice in from the chosen template."""
        if not self.template_id:
            return
        values = self.template_id._prepare_notification_values()
        for field_name, value in values.items():
            self[field_name] = value

    def action_toggle_flag(self):
        """Star or unstar for the person clicking, nobody else."""
        user = self.env.user
        for record in self.with_context(active_test=False):
            if user in record.flag_user_ids:
                record.sudo().flag_user_ids = [(3, user.id)]
            else:
                record.sudo().flag_user_ids = [(4, user.id)]

    # ── ACTIONS ───────────────────────────────────────────────────

    def action_schedule(self):
        for record in self:
            if record.state != 'draft':
                continue
            record.state = 'scheduled'
        self._arm_cron()

    # ── EXACT TIMING ──────────────────────────────────────────────

    def _arm_cron(self):
        """Ask the scheduler to wake up when these notices are due.

        The cron ticks every minute, so on its own it can be up to a minute
        late. This wakes it at the right moment instead. The browser still
        does the final, to-the-second timing (see the `upcoming` route).
        """
        moments = [
            record.notify_datetime for record in self
            if record.state == 'scheduled' and record.notify_datetime
        ]
        if not moments:
            return
        cron = self.env.ref(
            'velkio_reminders_notification.ir_cron_velkio_dispatch', raise_if_not_found=False
        )
        if cron:
            cron.sudo()._trigger(at=moments)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._arm_cron()
        return records

    # These belong to the reader, not to the notice: they are stored on that
    # person's own side record. Marking one read or starring it must not need
    # write access to a notice they are only allowed to read.
    _READER_FIELDS = frozenset({'flagged', 'is_read'})

    def write(self, vals):
        if vals and set(vals) <= self._READER_FIELDS:
            # sudo keeps the same uid, so the inverse still writes to the row
            # belonging to whoever is actually clicking. The read rules have
            # already limited self to notices they are allowed to see.
            result = super(VelkioNotification, self.sudo()).write(vals)
            # These fields depend on the uid, and Odoo keys that cache on
            # (uid, su) — so the value just written landed in the superuser's
            # slot. Drop both so the caller recomputes and sees its own.
            self.invalidate_recordset(list(self._READER_FIELDS))
            return result
        result = super().write(vals)
        if {'state', 'notify_datetime'} & set(vals):
            self._arm_cron()
        return result

    def is_due_for(self, user):
        """True when this notice may be put on that person's screen now.

        Used by the browser when its own timer goes off, so a cancelled or
        rescheduled notice is never shown.
        """
        self.ensure_one()
        if self.state not in ('scheduled', 'sent'):
            return False
        if not self.notify_datetime or self.notify_datetime > fields.Datetime.now():
            return False
        return user in self._get_audience()

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_send_now(self):
        """Push it to the screens straight away."""
        self.ensure_one()
        if self.state == 'cancelled':
            raise UserError(_('This notification was cancelled.'))
        # An explicit re-send reaches everyone, answered or not.
        self._dispatch(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sent'),
                'message': _('Shown to %s person(s).') % self.recipient_count,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_recipients(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recipients'),
            'res_model': 'velkio.notification.recipient',
            'view_mode': 'tree',
            'domain': [('notification_id', '=', self.id)],
        }

    # ── DELIVERY ──────────────────────────────────────────────────

    def _get_audience(self):
        """Resolve who should see this popup."""
        self.ensure_one()
        if self.audience == 'me':
            return self.create_uid
        if self.audience == 'all':
            return self.env['res.users'].search([
                ('active', '=', True), ('share', '=', False),
            ])
        return self.user_ids.filtered(lambda u: u.active and not u.share)

    def _style_payload(self):
        """The look to use: this notice's own style, else the default one."""
        self.ensure_one()
        if self.style_id:
            return self.style_id._as_payload()
        return self.env['velkio.popup.style'].default_payload()

    def _payload(self, user, style=None):
        """The dict the browser turns into a popup."""
        self.ensure_one()
        # A notice that demands an answer never counts itself down: the
        # countdown only exists to close the popup automatically.
        duration = 0 if self.require_ack else max(self.duration or 0, 0)
        return {
            'id': self.id,
            'title': self.name,
            'body': self.body or '',
            'level': self.level,
            'duration': duration,
            'require_ack': self.require_ack,
            'allow_snooze': self.allow_snooze and not self.require_ack,
            'sound': self.play_sound and user.velkio_sound_enabled,
            'author': self.create_uid.name or '',
            'is_self': user.id == self.create_uid.id,
            'shown_at': fields.Datetime.to_string(fields.Datetime.now()),
            # The operating system shows plain text, never markup.
            'desktop': user.velkio_desktop_enabled,
            'desktop_body': (html2plaintext(self.body) if self.body else '')[:220],
            # Shown beside the entry in the operating system's notification list.
            'icon': '/velkio_reminders_notification/static/description/icon.png',
            'style': style if style is not None else self._style_payload(),
        }

    # A reader in one of these states has already been served: the popup was
    # put on their screen and they either saw it, answered it or put it off.
    _SERVED_STATES = ('seen', 'done', 'snoozed')

    def _dispatch(self, force=False):
        """Create the recipient rows and push the popup to every screen.

        Both steps are done in one batch, so notifying the whole company costs
        a couple of queries rather than a couple per person.

        Anyone already served is left alone. The browser arms its own timer so
        a notice lands on the exact second, which is up to a minute before the
        cron catches up; without this the cron would reset their row and push
        the very same popup at them a second time.

        :param force: send to everyone again, including readers who have
            already answered. Used by the explicit "Send Now" button.
        """
        self.ensure_one()
        users = self._get_audience()
        if not users:
            _logger.info('Velkio notification %s has nobody to notify.', self.id)
            self.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
            return

        now = fields.Datetime.now()
        Recipient = self.env['velkio.notification.recipient'].sudo()
        existing = {r.user_id.id: r for r in self.recipient_ids.sudo()}
        # Resolve the look once for the whole audience, not once per person.
        style = self._style_payload()

        to_create, notifications = [], []
        for user in users:
            row = existing.get(user.id)
            if row and not force and row.state in self._SERVED_STATES:
                continue
            if not user.velkio_popup_enabled and self.level != 'urgent':
                # The reader switched popups off. Urgent notices ignore that.
                state = 'muted'
            else:
                state = 'sent'
                notifications.append(
                    (user.partner_id, 'velkio_notification', self._payload(user, style))
                )
            if row:
                row.write({'state': state, 'sent_at': now})
            else:
                to_create.append({
                    'notification_id': self.id,
                    'user_id': user.id,
                    'partner_id': user.partner_id.id,
                    'state': state,
                    'sent_at': now,
                })
        if to_create:
            Recipient.create(to_create)
        if notifications:
            self.env['bus.bus']._sendmany(notifications)

        self.write({'state': 'sent', 'sent_at': now})

    def _notify_closed(self, user):
        """Tell this user's other devices to take the popup down.

        The message carries the count rather than leaving each device to
        decrement its own: taking a card off the screen does not always mean
        one fewer unread, and the server is the one that knows.
        """
        self.ensure_one()
        self.env['bus.bus']._sendone(
            user.partner_id, 'velkio_notification_close',
            {'id': self.id, 'count': self._unread_count_for(user)},
        )

    def _unread_count_for(self, user):
        return self.env['velkio.notification.recipient']._unread_count(user)

    def _notify_closed_many(self, user):
        """Take a whole set of popups down on this user's other devices."""
        if not self:
            return
        count = self._unread_count_for(user)
        self.env['bus.bus']._sendmany([
            (user.partner_id, 'velkio_notification_close',
             {'id': notice.id, 'count': count})
            for notice in self
        ])

    def _resend_to_user(self, user):
        """Show it again to one person (used when a snooze runs out)."""
        self.ensure_one()
        if self.state == 'cancelled':
            return False
        self.env['bus.bus']._sendone(
            user.partner_id, 'velkio_notification', self._payload(user)
        )
        return True

    # ── DASHBOARD ─────────────────────────────────────────────────

    @api.model
    def _dashboard_domains(self):
        """The buckets shown on the dashboard, in display order.

        Domains live here rather than in the browser so the list you open is
        always the exact set that was counted.
        """
        user = self.env.user
        tz = user.tz or 'UTC'
        now_local = self._to_user_tz(fields.Datetime.now(), tz)
        day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        start_utc = self._to_utc(day_start, tz)
        end_utc = self._to_utc(day_end, tz)

        return [
            {
                'key': 'today', 'label': _('Today'), 'icon': 'fa-calendar-o',
                'accent': 'blue',
                'help': _('Due at some point today'),
                'domain': [
                    ('notify_datetime', '>=', fields.Datetime.to_string(start_utc)),
                    ('notify_datetime', '<', fields.Datetime.to_string(end_utc)),
                ],
            },
            {
                'key': 'scheduled', 'label': _('Scheduled'), 'icon': 'fa-clock-o',
                'accent': 'indigo',
                'help': _('Waiting for their moment'),
                'domain': [('state', '=', 'scheduled')],
            },
            {
                'key': 'assigned', 'label': _('Assigned to Me'), 'icon': 'fa-inbox',
                'accent': 'teal',
                'help': _('Sent to you and not answered yet'),
                'domain': [
                    ('recipient_ids.user_id', '=', user.id),
                    ('recipient_ids.state', 'in', ('sent', 'seen', 'snoozed')),
                ],
            },
            {
                'key': 'flagged', 'label': _('Flagged'), 'icon': 'fa-star',
                'accent': 'amber',
                'help': _('Starred for follow-up'),
                'domain': [('flagged', '=', True)],
            },
            {
                'key': 'urgent', 'label': _('Urgent'), 'icon': 'fa-exclamation-triangle',
                'accent': 'red',
                'help': _('Highest level notices'),
                'domain': [('level', '=', 'urgent')],
            },
            {
                'key': 'completed', 'label': _('Completed'), 'icon': 'fa-check-circle',
                'accent': 'green',
                'help': _('Already answered'),
                'domain': [
                    ('recipient_ids.user_id', '=', user.id),
                    ('recipient_ids.state', '=', 'done'),
                ],
            },
            {
                'key': 'all', 'label': _('All Reminders'), 'icon': 'fa-list-ul',
                'accent': 'slate',
                'help': _('Everything you can see'),
                'domain': [],
            },
        ]

    @api.model
    def get_dashboard_data(self):
        """Counts for each bucket, plus the domain that produced them."""
        buckets = []
        for bucket in self._dashboard_domains():
            buckets.append(dict(bucket, count=self.search_count(bucket['domain'])))
        return {
            'buckets': buckets,
            'next_up': self._dashboard_next_up(),
        }

    @api.model
    def _dashboard_next_up(self):
        """The handful of notices coming up next, for the dashboard list."""
        records = self.search([
            ('state', '=', 'scheduled'),
            ('notify_datetime', '>=', fields.Datetime.now()),
        ], order='notify_datetime asc', limit=6)
        return [{
            'id': record.id,
            'name': record.name,
            'level': record.level,
            'flagged': record.flagged,
            'audience': record.audience,
            'notify_datetime': fields.Datetime.to_string(record.notify_datetime),
        } for record in records]

    @api.model
    def _to_user_tz(self, value, tz_name):
        return pytz.utc.localize(value).astimezone(self._tz(tz_name))

    @api.model
    def _to_utc(self, value, tz_name):
        if value.tzinfo is None:
            value = self._tz(tz_name).localize(value)
        return value.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _tz(self, tz_name):
        try:
            return pytz.timezone(tz_name or 'UTC')
        except Exception:
            return pytz.UTC

    # ── CRON ──────────────────────────────────────────────────────

    @api.model
    def _cron_dispatch(self):
        """Every minute: send what is due, and wake up finished snoozes."""
        now = fields.Datetime.now()
        due = self.search([
            ('state', '=', 'scheduled'),
            ('notify_datetime', '<=', now),
        ])
        for notification in due:
            # A savepoint per notification: one bad record is rolled back on
            # its own and the rest still go out. Committing here instead would
            # end the caller's transaction, which breaks any code that calls
            # this inside one.
            try:
                with self.env.cr.savepoint():
                    notification._dispatch()
            except Exception:
                _logger.exception('Velkio notification %s failed to send', notification.id)
        self.env['velkio.notification.recipient']._cron_wake_snoozed()
