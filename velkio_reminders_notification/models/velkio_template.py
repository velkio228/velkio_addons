# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _


class VelkioTemplate(models.Model):
    """A ready-made notice: pick one, adjust the time, send it."""

    _name = 'velkio.template'
    _description = 'Notification Template'
    _order = 'category, sequence, name'

    name = fields.Char(string='Template', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection([
        ('personal', 'Personal Reminder'),
        ('meeting', 'Meetings'),
        ('deadline', 'Deadlines'),
        ('finance', 'Finance'),
        ('hr', 'People & HR'),
        ('it', 'IT & Maintenance'),
        ('safety', 'Health & Safety'),
        ('sales', 'Sales & CRM'),
        ('purchase', 'Purchase & Stock'),
        ('project', 'Projects & Support'),
    ], string='Category', required=True, default='personal')

    title = fields.Char(string='Popup Title', required=True)
    body = fields.Html(string='Message', required=True, sanitize=True)
    level = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Important'),
        ('urgent', 'Urgent'),
    ], string='Level', default='info', required=True)

    duration = fields.Integer(string='Auto-close After (seconds)', default=20)
    require_ack = fields.Boolean(string='Require Acknowledgement')
    allow_snooze = fields.Boolean(string='Allow Snooze', default=True)
    play_sound = fields.Boolean(string='Play Sound', default=True)
    lead_minutes = fields.Integer(
        string='Suggested Lead Time (minutes)', default=15,
        help='When used, the notice is pre-set this many minutes from now.'
    )

    usage_count = fields.Integer(string='Times Used', readonly=True, default=0, copy=False)
    color = fields.Integer(string='Colour')

    def _prepare_notification_values(self):
        """The values this template hands to a new notification."""
        self.ensure_one()
        return {
            'name': self.title,
            'body': self.body,
            'level': self.level,
            'duration': self.duration,
            'require_ack': self.require_ack,
            'allow_snooze': self.allow_snooze,
            'play_sound': self.play_sound,
            'notify_datetime': fields.Datetime.now() + timedelta(
                minutes=max(self.lead_minutes or 0, 1)
            ),
        }

    def action_use(self):
        """Open a new notification already filled in from this template."""
        self.ensure_one()
        # sudo: everyone may read the library, but not write the counter.
        self.sudo().usage_count += 1
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Notification'),
            'res_model': 'velkio.notification',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_template_id': self.id,
                'default_audience': 'me',
            },
        }
