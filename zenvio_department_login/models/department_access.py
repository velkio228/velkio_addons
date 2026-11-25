from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command

from .access_profile import GLOBAL_FLAGS, LINE_FIELDS, FIELD_LABELS

ROLES = [('user', 'User'), ('manager', 'Manager')]
ICONS = [
    ('fa-building', 'Building'), ('fa-cogs', 'Production'), ('fa-shopping-cart', 'Sales'),
    ('fa-cubes', 'Stores'), ('fa-truck', 'Logistics'), ('fa-shopping-bag', 'Purchase'),
    ('fa-calculator', 'Accounts'), ('fa-users', 'HR'), ('fa-wrench', 'Maintenance'),
    ('fa-flask', 'Quality'), ('fa-pencil-square-o', 'Design'), ('fa-laptop', 'IT'),
]


class ZenvioDepartmentAccess(models.Model):
    """A department inside a Top Management user (``owner_id``).

    Every employee mapped in ``line_ids`` logs in as the Top Management user with their
    own code and password; the module never creates users. What the employee
    can do is narrowed by the access profile of their role (User / Manager),
    or by their own profile when one is set on their line. A Top Management user
    sees only its own departments.
    """
    _name = 'zenvio.department.access'
    _description = 'Department Access'
    _inherit = ['mail.thread']
    _order = 'sequence, id'

    _department_uniq = models.Constraint(
        'UNIQUE(department_id)',
        'This department already has a department login.',
    )

    name = fields.Char(related='department_id.name')
    sequence = fields.Integer(default=10)
    owner_id = fields.Many2one(
        'res.users', string='Top Management', required=True, index=True, ondelete='restrict', tracking=True,
        default=lambda self: self.env.user, domain=lambda self: self._owner_domain(),
        help="User the employees of this department sign in through. They never get more rights than this user.")
    department_id = fields.Many2one(
        'hr.department', string='Department', required=True, ondelete='restrict', tracking=True,
        help="Choose an existing department or type a new name to create it.")
    user_profile_id = fields.Many2one(
        'zenvio.access.profile', string='User Access', tracking=True, ondelete='restrict',
        help="Access of the employees with the User role. Empty: the Top Management user's full rights.")
    manager_profile_id = fields.Many2one(
        'zenvio.access.profile', string='Manager Access', tracking=True, ondelete='restrict',
        help="Access of the employees with the Manager role. Empty: the Top Management user's full rights.")
    # The rules of each role, edited right on the department (stored in its
    # profile): user_readonly, manager_hide_menu_ids, user_field_line_ids ...
    for _zenvio_role in ('user', 'manager'):
        for _zenvio_key in GLOBAL_FLAGS + ('hide_menu_ids',) + tuple(LINE_FIELDS):
            _zenvio_type = (fields.Many2many if _zenvio_key == 'hide_menu_ids'
                            else fields.One2many if _zenvio_key in LINE_FIELDS else fields.Boolean)
            locals()[f'{_zenvio_role}_{_zenvio_key}'] = _zenvio_type(
                related=f'{_zenvio_role}_profile_id.{_zenvio_key}', readonly=False,
                string=f"{_zenvio_role.title()}: {FIELD_LABELS[_zenvio_key]}")
    del _zenvio_role, _zenvio_key, _zenvio_type  # loop names must not become class attributes (e.g. _name)
    line_ids = fields.One2many('zenvio.department.employee', 'access_id', string='Employees')
    employee_count = fields.Integer(compute='_compute_employee_count')
    log_ids = fields.One2many('zenvio.department.login.log', 'access_id', string='Login Log')
    log_count = fields.Integer(compute='_compute_log_count')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    color = fields.Integer()
    icon = fields.Selection(ICONS, default='fa-building', required=True,
                            help="Icon shown on the department card.")
    active = fields.Boolean(default=True, tracking=True)

    @api.model
    def _owner_domain(self):
        return [('all_group_ids', 'in', self.env.ref('zenvio_department_login.group_department_manager').ids)]

    @api.constrains('owner_id')
    def _check_owner(self):
        for access in self:
            if access.owner_id.share:
                raise ValidationError(_("%s is not an internal user and cannot be Top Management.", access.owner_id.name))

    @api.depends('line_ids.active')
    def _compute_employee_count(self):
        for access in self:
            access.employee_count = len(access.line_ids.filtered('active'))

    def _compute_log_count(self):
        counts = dict(self.env['zenvio.department.login.log']._read_group(
            [('access_id', 'in', self.ids)], ['access_id'], ['__count']))
        for access in self:
            access.log_count = counts.get(access, 0)

    @api.model_create_multi
    def create(self, vals_list):
        Profile = self.env['zenvio.access.profile']
        for vals in vals_list:
            owner = vals.get('owner_id') or self.env.user.id
            name = self.env['hr.department'].browse(vals.get('department_id')).name or ''
            for role, field in (('user', 'user_profile_id'), ('manager', 'manager_profile_id')):
                if not vals.get(field):
                    vals[field] = Profile.create({'name': f"{name} - {dict(ROLES)[role]}", 'owner_id': owner}).id
        accesses = super().create(vals_list)
        # A different card color for each new department.
        for access, vals in zip(accesses, vals_list):
            if 'color' not in vals:
                access.color = access.id % 11 + 1
        return accesses

    def write(self, vals):
        res = super().write(vals)
        if 'owner_id' in vals:
            profiles = self.user_profile_id | self.manager_profile_id | self.line_ids.profile_id
            profiles.write({'owner_id': vals['owner_id']})
        if {'user_profile_id', 'manager_profile_id', 'active'} & set(vals):
            self.env.registry.clear_cache()
        return res

    def _ensure_role_profiles(self):
        """Give departments created before 19.0.7.1 a profile per role."""
        Profile = self.env['zenvio.access.profile']
        for access in self:
            for role, field in (('user', 'user_profile_id'), ('manager', 'manager_profile_id')):
                if not access[field]:
                    access[field] = Profile.create({
                        'name': f"{access.name} - {dict(ROLES)[role]}", 'owner_id': access.owner_id.id})

    def unlink(self):
        profiles = self.user_profile_id | self.manager_profile_id | self.with_context(active_test=False).line_ids.profile_id
        res = super().unlink()
        profiles.exists().unlink()
        return res

    def _role_profile(self, role):
        self.ensure_one()
        return self.manager_profile_id if role == 'manager' else self.user_profile_id

    def action_load_department_employees(self):
        """Map every employee of the department (and its sub-departments)
        who is not in this department login yet."""
        for access in self:
            mapped = access.with_context(active_test=False).line_ids.employee_id
            employees = self.env['hr.employee'].search([
                ('department_id', 'child_of', access.department_id.id),
                ('id', 'not in', mapped.ids),
            ])
            access.line_ids = [Command.create({'employee_id': employee.id}) for employee in employees]
        return True

    def action_view_employees(self):
        """Employees of this department and their login codes."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("%s – Employees", self.name),
            'res_model': 'zenvio.department.employee',
            'view_mode': 'list',
            'domain': [('access_id', '=', self.id)],
            'context': {'default_access_id': self.id, 'active_test': False},
            'target': 'new',
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Login Log'),
            'res_model': 'zenvio.department.login.log',
            'view_mode': 'list,form',
            'domain': [('access_id', '=', self.id)],
            'context': {'default_access_id': self.id},
        }
