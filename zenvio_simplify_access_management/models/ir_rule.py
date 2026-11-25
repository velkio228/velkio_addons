# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import  ValidationError, UserError
from odoo.tools import config
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.http import request
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from .domain_prepare import prepare_domain_v2

class ir_rule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    @tools.conditional(
        'xml' not in config['dev_mode'],
        tools.ormcache('self.env.uid', 'self.env.su', 'model_name', 'mode',
                       'tuple(self._compute_domain_context_values())'),
    )
    def _compute_domain(self, model_name, mode="read"):
        res = super(ir_rule, self)._compute_domain(model_name, mode)

        AccessManagement = self.env['access.management'].sudo()
        if not AccessManagement._zenvio_engine_active():
            return res  # not installed yet, or being uninstalled
        model_list = ['mail.activity', 'res.users.log', 'res.users', 'mail.channel', 'mail.alias', 'bus.presence',
                      'res.lang']

        # Read-only users may not change anything (checked only for users who have
        # such a rule, and never while modules are being installed or upgraded).
        if (mode != 'read' and self.env.user.id and model_name not in model_list
                and model_name not in ['mail.channel.partner']
                and AccessManagement._has_readonly_restriction_any_company()):
            self._cr.execute("SELECT 1 FROM ir_module_module WHERE state IN ('to upgrade', 'to remove', 'to install') LIMIT 1")
            if not self._cr.fetchone():
                raise UserError(
                    _('%s is a read-only user. So you can not make any changes in the system!') % self.env.user.name)

        if model_name and self.env.user:
                    try:
                        access_domain_ah_ids = self.env['access.domain.ah'].browse(
                            AccessManagement._zenvio_domain_line_ids(model_name, True))
                    except Exception:
                        access_domain_ah_ids = False
                    if access_domain_ah_ids:
                        domain_list = []
                        if model_name == 'res.partner':
                            # jo aya user related jetala partner 6 ana access alag thi apididha 6 error no ave atle
                            self._cr.execute("""SELECT partner_id FROM res_users""")
                            partner_ids = [row[0] for row in self._cr.fetchall()]
                            domain_list = ['|', ('id', 'in', partner_ids)]
                        left_user = False
                        eval_context = self._eval_context()
                        # only domain records
                        length = len(access_domain_ah_ids.sudo()) if access_domain_ah_ids.sudo() else 0
                        for access in access_domain_ah_ids.sudo():
                            dom = safe_eval(access.domain, eval_context) if access.domain else []
                            if dom:
                                dom = expression.normalize_domain(dom)
                                for dom_tuple in dom:
                                    if isinstance(dom_tuple, tuple):
                                        left_value = dom_tuple[0]
                                        operator_value = dom_tuple[1]
                                        right_value = dom_tuple[2]
                                        left_value_split_list = left_value.split('.')
                                        model_string = model_name
                                        left_user = False
                                        left_company = False
                                        for field in left_value_split_list:
                                            left_user = False
                                            left_company = False
                                            model_obj = self.env[model_string]
                                            field_type = model_obj.fields_get()[field]['type']
                                            if field_type in ['many2one', 'many2many', 'one2many']:
                                                field_relation = model_obj.fields_get()[field]['relation']
                                                model_string = field_relation
                                                if model_string == 'res.users':
                                                    left_user = True
                                                if model_string == 'res.company':
                                                    left_company = True

                                        if left_user:
                                            if operator_value in ['in', 'not in']:
                                                if isinstance(right_value, list) and 0 in right_value:
                                                    zero_index = right_value.index(0)
                                                    right_value[zero_index] = self.env.user.id

                                        if left_company:
                                            if operator_value in ['in', 'not in']:
                                                if isinstance(right_value, list) and 0 in right_value:
                                                    zero_index = right_value.index(0)
                                                    right_value[zero_index] = self.env.company.id

                                        if operator_value == 'date_filter':
                                            domain_list += prepare_domain_v2(dom_tuple)
                                        else:
                                            domain_list.append(dom_tuple)
                                    else:
                                        domain_list.append(dom_tuple)
                                if length > 1:
                                    domain_list.insert(0, '|')
                                    length -= 1
                        if domain_list:
                            return domain_list

        return res
