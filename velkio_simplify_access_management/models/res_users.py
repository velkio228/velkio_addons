from odoo import fields, models, api, _
from odoo.exceptions import UserError, AccessDenied
import logging
_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_management_ids = fields.Many2many('access.management', 'access_management_users_rel_ah', 'user_id',
                                             'access_management_id', 'Access Pack')

    velkio_access_tag_color = fields.Integer(
        string="Access Tag Color",
        compute="_compute_velkio_access_tag_color",
        help="Stable colour index (1-11) used to colour this user's tag in the "
             "Access Management screens. Derived from the user id, so each user "
             "always keeps the same colour.")

    @api.depends('login')
    def _compute_velkio_access_tag_color(self):
        for user in self:
            uid = user.id
            user.velkio_access_tag_color = (uid % 11) + 1 if isinstance(uid, int) and uid else 0

    def write(self, vals):
        res = super().write(vals)
        if 'access_management_ids' in vals:
            # keep the per-user view/ACL caches in sync when packs are assigned
            # from the user form (the access.management form clears it itself)
            self.env.registry.clear_cache()
        for access in self.access_management_ids:
            if self.env.company in access.company_ids and access.readonly:
                if self.has_group('base.group_system') or self.has_group('base.group_erp_manager'):
                    raise UserError(_('Admin user can not be set as a read-only..!'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if any('access_management_ids' in v for v in vals_list):
            self.env.registry.clear_cache()
        for record in res:
            for access in record.access_management_ids:
                if self.env.company in access.company_ids and access.readonly:
                    if record.has_group('base.group_system') or record.has_group('base.group_erp_manager'):
                        raise UserError(_('Admin user can not be set as a read-only..!'))
        return res

    def _check_credentials(self, credential, user_agent_env):
        """ Odoo 18 turned ``_login`` into ``_login(cls, db, credential, user_agent_env)``
        with a credential dict and moved credential validation into
        ``_check_credentials``. Enforce the "Disable Login" rule here: ``self`` is the
        user being authenticated. """
        res = super()._check_credentials(credential, user_agent_env)
        blocked = self.sudo().env['access.management'].search_count([
            ('user_ids', 'in', self.id),
            ('active', '=', True),
            ('disable_login', '=', True),
        ])
        if blocked:
            _logger.info("Login refused by Access Management (Disable Login) for uid:%s", self.id)
            raise AccessDenied()
        return res
