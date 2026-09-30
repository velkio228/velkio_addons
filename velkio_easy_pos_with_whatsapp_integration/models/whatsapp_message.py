# -*- coding: utf-8 -*-
from odoo import api, models

# whatsapp.message state -> pos.screen.order whatsapp_state
_STATE_MAP = {
    'outgoing': 'queued',
    'sent': 'sent',
    'delivered': 'sent',
    'read': 'sent',
    'error': 'failed',
    'cancel': 'failed',
}


class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        messages._sync_pos_screen_orders()
        return messages

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            self._sync_pos_screen_orders()
        return result

    def _sync_pos_screen_orders(self):
        """Mirror Meta's answer on the bills these messages were sent from.

        The bill is found through the chatter message, so a send from the
        counter, from the bill form's composer, all count. Older messages cannot replace the most recently
        created tracked message when a delayed delivery callback arrives.
        """
        Order = self.env['pos.screen.order'].sudo()
        for message in self:
            mail = message.mail_message_id
            if (message.message_type != 'outbound' or not mail
                    or mail.model != Order._name or not mail.res_id):
                continue
            order = Order.browse(mail.res_id).exists()
            state = _STATE_MAP.get(message.state)
            if not order or not state:
                continue
            if order.whatsapp_message_id and message.id < order.whatsapp_message_id.id:
                continue
            error = False
            if state == 'failed':
                error = (message.failure_reason
                         or dict(message._fields['failure_type'].selection)
                         .get(message.failure_type)
                         or message.state)[:250]
            if (order.whatsapp_message_id == message
                    and order.whatsapp_state == state
                    and (order.whatsapp_error or False) == error):
                continue
            order.write({
                'whatsapp_message_id': message.id,
                'whatsapp_state': state,
                'whatsapp_error': error,
            })
