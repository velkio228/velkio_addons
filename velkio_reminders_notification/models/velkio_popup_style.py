# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# Ready-made looks. Picking one fills the detailed settings below it, which the
# administrator is then free to adjust.
PRESETS = {
    'card': {
        'skin': 'card', 'surface': 'solid', 'appearance': 'light', 'radius': 24,
        'shadow': 'deep', 'animation': 'drop', 'position': 'top-center',
        'show_icon': True, 'show_level_chip': True, 'show_progress': True,
        'compact': False, 'width': 470,
    },
    'neumorph': {
        'skin': 'neumorph', 'surface': 'solid', 'appearance': 'light', 'radius': 26,
        'shadow': 'none', 'animation': 'pop', 'position': 'top-center',
        'show_icon': True, 'show_level_chip': False, 'show_progress': False,
        'compact': False, 'width': 420,
    },
    'alert_solid': {
        'skin': 'alert_solid', 'surface': 'solid', 'appearance': 'light', 'radius': 20,
        'shadow': 'deep', 'animation': 'zoom', 'position': 'top-center',
        'show_icon': True, 'show_level_chip': False, 'show_progress': True,
        'compact': False, 'width': 420,
    },
    'alert_outline': {
        'skin': 'alert_outline', 'surface': 'solid', 'appearance': 'light', 'radius': 22,
        'shadow': 'soft', 'animation': 'rise', 'position': 'top-center',
        'show_icon': True, 'show_level_chip': False, 'show_progress': False,
        'compact': False, 'width': 420,
    },
    'alert_dashed': {
        'skin': 'alert_dashed', 'surface': 'solid', 'appearance': 'light', 'radius': 22,
        'shadow': 'none', 'animation': 'flip', 'position': 'top-center',
        'show_icon': True, 'show_level_chip': False, 'show_progress': False,
        'compact': False, 'width': 420,
    },
    'strip': {
        'skin': 'strip', 'surface': 'solid', 'appearance': 'dark', 'radius': 14,
        'shadow': 'deep', 'animation': 'slide', 'position': 'bottom-right',
        'show_icon': True, 'show_level_chip': False, 'show_progress': True,
        'compact': True, 'width': 460,
    },
}


class VelkioPopupStyle(models.Model):
    """How the floating popup looks and where it appears.

    Everything here ends up as CSS custom properties on the card, so a change
    takes effect on the next popup without touching a stylesheet.
    """

    _name = 'velkio.popup.style'
    _description = 'Popup Style'
    _order = 'is_default desc, name'

    name = fields.Char(string='Style Name', required=True)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Default Style',
        help='Used for every notification that does not choose its own style.'
    )
    skin = fields.Selection([
        ('card', 'Reminder Card — bell, centred, friendly'),
        ('neumorph', 'Soft Relief — raised card, floating icon'),
        ('alert_solid', 'Solid Alert — filled colour, white text'),
        ('alert_outline', 'Outline Alert — white card, bold border'),
        ('alert_dashed', 'Dashed Alert — white card, dashed border'),
        ('strip', 'Strip — compact bar, icon beside the text'),
    ], string='Design', default='card', required=True,
        help='The overall shape of the popup. Each design is a different '
             'layout, not just a different colour.')
    preset = fields.Selection([
        ('card', 'Reminder Card'),
        ('neumorph', 'Soft Relief'),
        ('alert_solid', 'Solid Alert'),
        ('alert_outline', 'Outline Alert'),
        ('alert_dashed', 'Dashed Alert'),
        ('strip', 'Strip'),
        ('custom', 'Custom'),
    ], string='Preset', default='card', required=True)

    # ── placement ─────────────────────────────────────────────
    position = fields.Selection([
        ('top-right', 'Top right'),
        ('top-center', 'Top centre'),
        ('top-left', 'Top left'),
        ('bottom-right', 'Bottom right'),
        ('bottom-left', 'Bottom left'),
        ('center', 'Middle of the screen'),
    ], string='Position', default='top-center', required=True)
    width = fields.Integer(string='Width (px)', default=470)
    stack_limit = fields.Integer(
        string='Max Popups on Screen', default=1,
        help='How many cards may sit on screen together. One is usually right: '
             'the cards are large, and anything beyond this waits behind a '
             '"more waiting" chip and in the bell.'
    )

    # ── surface ───────────────────────────────────────────────
    appearance = fields.Selection([
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Follow the device'),
    ], string='Appearance', default='light', required=True)
    surface = fields.Selection([
        ('glass', 'Frosted glass'),
        ('solid', 'Solid'),
        ('gradient', 'Gradient tint'),
    ], string='Surface', default='glass', required=True)
    radius = fields.Integer(string='Corner Radius (px)', default=24)
    shadow = fields.Selection([
        ('none', 'Flat'),
        ('soft', 'Soft'),
        ('deep', 'Deep'),
    ], string='Shadow', default='deep', required=True)

    # ── colour ────────────────────────────────────────────────
    accent_mode = fields.Selection([
        ('level', 'One colour per level'),
        ('custom', 'Always this colour'),
    ], string='Accent', default='level', required=True)
    accent_color = fields.Char(string='Accent Colour', default='#2563eb')
    color_info = fields.Char(string='Information', default='#2563eb')
    color_warning = fields.Char(string='Important', default='#d97706')
    color_urgent = fields.Char(string='Urgent', default='#dc2626')

    # ── motion ────────────────────────────────────────────────
    animation = fields.Selection([
        ('drop', 'Drop from the top'),
        ('slide', 'Slide in from the side'),
        ('rise', 'Rise from the bottom'),
        ('zoom', 'Zoom in'),
        ('pop', 'Pop'),
        ('flip', 'Flip in'),
        ('bounce', 'Bounce in'),
        ('fade', 'Fade in'),
        ('none', 'No animation'),
    ], string='Entrance', default='drop', required=True)

    # ── elements ──────────────────────────────────────────────
    show_icon = fields.Boolean(string='Show Icon', default=True)
    show_level_chip = fields.Boolean(string='Show Level Tag', default=True)
    show_author = fields.Boolean(string='Show Sender', default=True)
    show_progress = fields.Boolean(string='Show Countdown Bar', default=True)
    compact = fields.Boolean(
        string='Compact Layout',
        help='Tighter spacing and smaller text, for a denser popup.'
    )

    _sql_constraints = [
        ('width_sane', 'CHECK (width BETWEEN 280 AND 640)',
         'Popup width must be between 280 and 640 pixels.'),
        ('radius_sane', 'CHECK (radius BETWEEN 0 AND 32)',
         'Corner radius must be between 0 and 32 pixels.'),
        ('stack_sane', 'CHECK (stack_limit BETWEEN 1 AND 10)',
         'Between 1 and 10 popups may be on screen at once.'),
    ]

    @api.constrains('is_default')
    def _check_single_default(self):
        for style in self:
            if not style.is_default:
                continue
            others = self.search([('is_default', '=', True), ('id', '!=', style.id)])
            if others:
                others.is_default = False

    @api.constrains('accent_color', 'color_info', 'color_warning', 'color_urgent')
    def _check_colours(self):
        for style in self:
            for field_name in ('accent_color', 'color_info', 'color_warning', 'color_urgent'):
                value = style[field_name] or ''
                if value and not (value.startswith('#') and len(value) in (4, 7)):
                    raise ValidationError(_(
                        'Colours must be written as a hex code, for example #2563eb.'
                    ))

    @api.onchange('preset')
    def _onchange_preset(self):
        """Filling in a preset gives a sensible starting point to tweak."""
        values = PRESETS.get(self.preset)
        if not values:
            return
        for field_name, value in values.items():
            self[field_name] = value

    @api.model
    def get_default_style(self):
        """The style to use when a notification does not name one."""
        style = self.sudo().search([('is_default', '=', True)], limit=1)
        return style or self.sudo().search([], limit=1)

    def _as_payload(self):
        """Everything the browser needs to paint the popup."""
        self.ensure_one()
        return {
            'skin': self.skin,
            'position': self.position,
            'width': self.width,
            'stack_limit': self.stack_limit,
            'appearance': self.appearance,
            'surface': self.surface,
            'radius': self.radius,
            'shadow': self.shadow,
            'animation': self.animation,
            'accent_mode': self.accent_mode,
            'accent_color': self.accent_color or '#2563eb',
            'colors': {
                'info': self.color_info or '#2563eb',
                'warning': self.color_warning or '#d97706',
                'urgent': self.color_urgent or '#dc2626',
            },
            'show_icon': self.show_icon,
            'show_level_chip': self.show_level_chip,
            'show_author': self.show_author,
            'show_progress': self.show_progress,
            'compact': self.compact,
        }

    @api.model
    def default_payload(self):
        """Payload of the default style, or built-in values if none exists."""
        style = self.get_default_style()
        if style:
            return style._as_payload()
        return {
            'skin': 'card',
            'position': 'top-center', 'width': 470, 'stack_limit': 1,
            'appearance': 'light', 'surface': 'solid', 'radius': 24,
            'shadow': 'deep', 'animation': 'drop', 'accent_mode': 'level',
            'accent_color': '#2563eb',
            'colors': {'info': '#2563eb', 'warning': '#d97706', 'urgent': '#dc2626'},
            'show_icon': True, 'show_level_chip': True, 'show_author': True,
            'show_progress': True, 'compact': False,
        }

    def action_preview(self):
        """Send a sample popup to the person editing the style."""
        self.ensure_one()
        user = self.env.user
        payload = {
            'id': -self.id,  # negative: a preview is not a real notification
            'title': _('This is how your popups will look'),
            'body': _('<p>A short message, with a <strong>bold</strong> word in it.</p>'),
            'level': 'info',
            'duration': 12,
            'require_ack': False,
            'allow_snooze': True,
            'sound': False,
            'author': user.name,
            'is_self': True,
            'preview': True,
            'style': self._as_payload(),
        }
        self.env['bus.bus']._sendone(user.partner_id, 'velkio_notification', payload)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Preview sent'),
                'message': _('Look at the corner of your screen.'),
                'type': 'info',
                'sticky': False,
            },
        }
