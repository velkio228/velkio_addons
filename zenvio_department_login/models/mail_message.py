from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        """Show the real employee in the chatter instead of the department user."""
        line = self.env['zenvio.department.employee']._get_session_line()
        partner = line.employee_id.work_contact_id
        if partner:
            user_partner_id = self.env.user.partner_id.id
            for vals in vals_list:
                if vals.get('author_id', user_partner_id) == user_partner_id:
                    vals['author_id'] = partner.id
        return super().create(vals_list)
