# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosScreenConfig(models.Model):
    _inherit = 'pos.screen.config'

    whatsapp_send_on_payment = fields.Boolean(
        string='Send Bill on WhatsApp',
        help='When a bill is paid, send the receipt to the customer WhatsApp '
             'number automatically.')
    whatsapp_template_id = fields.Many2one(
        'whatsapp.template', string='WhatsApp Template',
        domain="[('model', '=', 'pos.screen.order')]",
        help='Approved WhatsApp template used to send the bill. Meta only '
             'delivers business initiated messages through an approved '
             'template.')
    whatsapp_template_status = fields.Selection(
        related='whatsapp_template_id.status', string='Template Status',
        readonly=True)

    @api.constrains('whatsapp_send_on_payment', 'whatsapp_template_id')
    def _check_whatsapp_template(self):
        for config in self:
            if config.whatsapp_send_on_payment and not config.whatsapp_template_id:
                raise ValidationError(_(
                    'Counter %s sends bills on WhatsApp, so it needs a '
                    'WhatsApp template.', config.name))

    def _whatsapp_template(self):
        """Template to use, falling back to the one shipped by this module."""
        self.ensure_one()
        if self.whatsapp_template_id:
            return self.whatsapp_template_id
        return self.env.ref(
            'velkio_easy_pos_with_whatsapp_integration.whatsapp_template_pos_screen_bill',
            raise_if_not_found=False) or self.env['whatsapp.template']
