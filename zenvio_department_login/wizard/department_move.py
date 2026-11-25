from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZenvioDepartmentMove(models.TransientModel):
    """Move departments (with their employees, passwords and access rights)
    from one Top Management user to another."""
    _name = 'zenvio.department.move'
    _description = 'Move Departments to Another Top Management User'

    from_user_id = fields.Many2one('res.users', string='From', required=True, readonly=True)
    department_ids = fields.Many2many(
        'zenvio.department.access', string='Departments', required=True,
        domain="[('owner_id', '=', from_user_id)]",
        help="Departments to move. Their employees, login codes, passwords and access rights move with them.")
    to_user_id = fields.Many2one(
        'res.users', string='Move To', required=True,
        domain="[('share', '=', False), ('id', '!=', from_user_id)]",
        help="Internal user who takes over the departments. Becomes Top Management if not already.")
    remove_top_management = fields.Boolean(
        string='Remove Top Management from the current user',
        help="Turn off Top Management for the current user once all their departments are moved.")
    all_selected = fields.Boolean(compute='_compute_all_selected')
    employee_count = fields.Integer(compute='_compute_all_selected')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env['res.users'].browse(res.get('from_user_id') or self.env.context.get('active_id'))
        if user:
            res['from_user_id'] = user.id
            res.setdefault('department_ids', [(6, 0, user.with_context(active_test=False).zenvio_owned_department_ids.ids)])
            res.setdefault('remove_top_management', bool(self.env.context.get('zenvio_remove_top_management')))
        return res

    @api.depends('department_ids', 'from_user_id')
    def _compute_all_selected(self):
        for wizard in self:
            owned = wizard.from_user_id.with_context(active_test=False).zenvio_owned_department_ids
            wizard.all_selected = bool(owned) and not (owned - wizard.department_ids)
            wizard.employee_count = sum(wizard.department_ids.mapped('employee_count'))

    def action_move(self):
        self.ensure_one()
        if self.to_user_id == self.from_user_id:
            raise UserError(_("Choose another user to move the departments to."))
        if self.to_user_id.share:
            raise UserError(_("%s is not an internal user and cannot be Top Management.", self.to_user_id.name))
        if not self.to_user_id.zenvio_is_ceo:
            self.to_user_id.zenvio_is_ceo = True
        # Changing the owner also hands over the access rules, is logged in each
        # department's chatter, and ends the employees' open sessions: they log
        # in again, now through the new user.
        self.department_ids.write({'owner_id': self.to_user_id.id})
        if self.remove_top_management and not self.from_user_id.with_context(active_test=False).zenvio_owned_department_ids:
            self.from_user_id.zenvio_is_ceo = False
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
