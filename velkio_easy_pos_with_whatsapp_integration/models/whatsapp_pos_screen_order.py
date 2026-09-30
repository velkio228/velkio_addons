# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosScreenOrder(models.Model):
    _inherit = 'pos.screen.order'

    whatsapp_state = fields.Selection(
        [('none', 'Not Sent'),
         ('queued', 'Queued'),
         ('sent', 'Sent'),
         ('failed', 'Failed')],
        string='WhatsApp', default='none', copy=False, readonly=True)
    whatsapp_error = fields.Char(
        string='WhatsApp Error', copy=False, readonly=True)
    whatsapp_message_id = fields.Many2one(
        'whatsapp.message', string='WhatsApp Message', copy=False,
        readonly=True, index='btree_not_null',
        help='Last message sent for this bill; its delivery result from Meta '
             'is mirrored on the bill.')
    whatsapp_number_manual = fields.Char(
        string='Send To (override)',
        help='Send this bill to a different number than the customer record. '
             'Leave empty to use the customer number.')
    whatsapp_number = fields.Char(
        string='WhatsApp Number', compute='_compute_whatsapp_number',
        store=True)

    @api.depends('whatsapp_number_manual', 'partner_id.mobile',
                 'partner_id.phone', 'partner_id.name')
    def _compute_whatsapp_number(self):
        Order = self.env['pos.screen.order']
        for order in self:
            partner = order.partner_id
            # Walk-in counters often key a customer in as a bare phone
            # number, so a numeric NAME is a valid destination too.
            name_as_number = Order._normalize_phone(partner.name)
            order.whatsapp_number = (
                order.whatsapp_number_manual
                or partner.mobile
                or partner.phone
                or name_as_number
                or False
            )

    def _get_whatsapp_safe_fields(self):
        """Fields a WhatsApp template may read on this model."""
        # Both the bare m2o and the dotted path: a variable stores whichever
        # the template author picked, and this set is matched exactly.
        return {
            'name', 'amount_total', 'amount_untaxed', 'amount_tax',
            'partner_id', 'partner_id.name',
            'company_id', 'company_id.name',
            'currency_id.name', 'currency_id.symbol',
            'user_id', 'user_id.name',
            'config_id', 'config_id.name',
            'payment_method_id', 'payment_method_id.name',
            'payment_machine', 'date_order',
        }

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _whatsapp_blocking_reason(self):
        """Why this bill cannot be sent, or None when it can."""
        self.ensure_one()
        if self.state != 'paid':
            return _('only paid bills can be sent')
        if not self.whatsapp_number:
            if not self.partner_id:
                return _('the bill has no customer and no number')
            return _(
                '%s has no phone or mobile number, and the name is not a '
                'number either', self.partner_id.display_name)
        template = self.config_id._whatsapp_template() if self.config_id \
            else self.env['whatsapp.template']
        if not template:
            return _('no WhatsApp template is configured')
        if template.status != 'approved':
            return _(
                'template "%(name)s" is %(status)s, not approved by Meta',
                name=template.name, status=template.status)
        if not template.wa_account_id:
            return _('the template has no WhatsApp Business account')
        return None

    def _send_whatsapp_bill(self, raise_on_error=True):
        """Send the bill PDF to the customer over WhatsApp.

        Returns the number of bills actually handed to the WhatsApp queue.
        The bill stays 'queued' until Meta answers: whatsapp.message then
        moves it to 'sent' or 'failed' (see _sync_pos_screen_orders).
        """
        sent = 0
        for order in self:
            reason = order._whatsapp_blocking_reason()
            if reason:
                order.write({
                    'whatsapp_state': 'failed',
                    'whatsapp_error': reason,
                })
                if raise_on_error:
                    raise UserError(_(
                        'Cannot send %(bill)s on WhatsApp: %(reason)s.',
                        bill=order.name, reason=reason))
                continue

            template = order.config_id._whatsapp_template()
            try:
                with self.env.cr.savepoint():
                    composer = self.env['whatsapp.composer'].with_context(
                        active_model=order._name,
                        active_id=order.id,
                        active_ids=order.ids,
                    ).create({
                        'res_model': order._name,
                        'res_ids': str(order.ids),
                        'wa_template_id': template.id,
                        'phone': order.whatsapp_number,
                    })
                    # Queue rather than block the cashier on Meta's API: the
                    # screen must stay responsive at the counter.
                    messages = composer._send_whatsapp_template(
                        force_send_by_cron=True)
            except Exception as error:  # noqa: BLE001 - never block a paid bill
                _logger.warning(
                    'Velkio Easy POS: WhatsApp send failed for %s: %s',
                    order.name, error)
                order.write({
                    'whatsapp_state': 'failed',
                    'whatsapp_error': str(error)[:250],
                })
                if raise_on_error:
                    raise UserError(_(
                        'Cannot send %(bill)s on WhatsApp: %(error)s',
                        bill=order.name, error=error))
                continue

            if not messages:
                order.write({'whatsapp_state': 'failed', 'whatsapp_error': _('No WhatsApp message was queued.')})
                if raise_on_error:
                    raise UserError(_('No WhatsApp message was queued.'))
                continue
            order.write({
                'whatsapp_state': 'queued',
                'whatsapp_error': False,
                'whatsapp_message_id': messages[:1].id,
            })
            messages._sync_pos_screen_orders()
            order.message_post(body=_(
                'Bill queued on WhatsApp to %s.', order.whatsapp_number))
            sent += 1
        return sent

    def action_send_whatsapp(self):
        """Manual send from the bill form - opens the standard composer."""
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(_('Only paid bills can be sent on WhatsApp.'))
        template = self.config_id._whatsapp_template() if self.config_id \
            else self.env['whatsapp.template']
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Bill on WhatsApp'),
            'res_model': 'whatsapp.composer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
                'active_ids': self.ids,
                'default_res_model': self._name,
                'default_res_ids': str(self.ids),
                'default_wa_template_id': template.id or False,
                'default_phone': self.whatsapp_number or '',
            },
        }

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def action_mark_paid(self):
        self._lock_for_payment()
        newly_paid = self.filtered(lambda order: order.state != 'paid')
        result = super().action_mark_paid()
        for order in newly_paid:
            config = order.config_id
            if not config or not config.whatsapp_send_on_payment:
                continue
            # A WhatsApp problem must never undo a payment that already
            # took the money and moved the stock.
            try:
                with self.env.cr.savepoint():
                    order._send_whatsapp_bill(raise_on_error=False)
            except Exception as error:
                _logger.warning('Velkio Easy POS: automatic receipt failed for %s: %s', order.name, error)
                order.write({'whatsapp_state': 'failed', 'whatsapp_error': str(error)[:250]})
        return result

    @api.model
    def _prepare_order_vals(self, payload):
        """Carry a number typed at the counter onto the bill.

        Set here rather than after create_from_ui(): the payment hook that
        sends the message runs inside it, so a later write would be too late.
        """
        vals = super()._prepare_order_vals(payload)
        number = (payload or {}).get('whatsapp_number') or ''
        vals['whatsapp_number_manual'] = number or False
        return vals

    @api.model
    def create_from_ui(self, payload):
        """Tell the screen what happened to the WhatsApp message."""
        result = super().create_from_ui(payload)
        order = self.browse(result.get('order_id'))
        if order.exists() and order.whatsapp_state != 'none':
            if order.whatsapp_state == 'sent':
                result['whatsapp_status'] = _(
                    'WhatsApp sent to %s', order.whatsapp_number)
            elif order.whatsapp_state == 'queued':
                result['whatsapp_status'] = _(
                    'WhatsApp queued for %s', order.whatsapp_number)
            else:
                result['whatsapp_status'] = _(
                    'WhatsApp not sent (%s)', order.whatsapp_error or _('error'))
        return result

    @api.model
    def load_order(self, order_id):
        result = super().load_order(order_id)
        order = self.browse(order_id)
        result['whatsapp_number_manual'] = order.whatsapp_number_manual or ''
        result['whatsapp_state'] = order.whatsapp_state
        return result
