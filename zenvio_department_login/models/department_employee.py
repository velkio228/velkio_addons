from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import frozendict

from .access_profile import GLOBAL_FLAGS

from .department_access import ROLES

MIN_PASSWORD_LENGTH = 6
NO_RULES = frozendict({'id': False, 'version': '', 'hidden_menu_ids': frozenset(), 'models': frozendict(),
                       **dict.fromkeys(GLOBAL_FLAGS, False)})


class ZenvioDepartmentEmployee(models.Model):
    """An employee mapped under a department login, with their login code and password."""
    _name = 'zenvio.department.employee'
    _description = 'Department Access Employee'
    _order = 'access_id, employee_id'

    _department_employee_uniq = models.Constraint(
        'UNIQUE(access_id, employee_id)',
        'This employee is already in this department.',
    )
    _login_code_uniq = models.Constraint(
        'UNIQUE(login_code)',
        'Each employee login code must be unique.',
    )

    access_id = fields.Many2one(
        'zenvio.department.access', string='Department', required=True, ondelete='cascade', index=True)
    department_id = fields.Many2one(related='access_id.department_id', store=True, string='HR Department')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    role = fields.Selection(ROLES, string='Role', required=True, default='user',
                            help="User or Manager: decides which access profile of the department the employee works with.")
    profile_id = fields.Many2one(
        'zenvio.access.profile', string='Personal Access', ondelete='restrict',
        help="Access for this employee only. Empty: the access of their role in the department.")
    can_switch = fields.Boolean(
        string='Can Switch', default=False,
        help="This employee gets the Switch option in the top bar to open Odoo as other employees.")
    switch_access_ids = fields.Many2many(
        'zenvio.department.access', 'zenvio_department_employee_switch_rel', 'line_id', 'access_id',
        string='Switch Departments',
        help="Departments whose employees this employee can switch to. Empty: all departments of the same "
             "Top Management user.")
    login_code = fields.Char(
        string='Login Code', compute='_compute_login_code', store=True, readonly=False, required=True, precompute=True,
        help="Code the employee types on the employee login page (defaults to the badge ID).")
    password = fields.Char(
        string='Password', compute='_compute_password', inverse='_inverse_password',
        help="Type a new password (at least 6 characters) to set or change it. It is stored encrypted.")
    password_hash = fields.Char(copy=False, groups='base.group_system')  # read in sudo by the login check only
    has_password = fields.Boolean(string='Password Set', compute='_compute_has_password', store=True)
    last_login = fields.Datetime(readonly=True, copy=False)
    active = fields.Boolean(default=True)

    @api.depends('employee_id')
    def _compute_login_code(self):
        """Badge ID or ``E0012``; an employee who is in several departments
        gets ``E0012-2``, ``E0012-3`` ... so each code opens one department."""
        taken = set(self.sudo().with_context(active_test=False).search([]).mapped('login_code'))
        for line in self:
            if line.login_code or not line.employee_id:
                continue
            base = (line.employee_id.barcode or f"E{line.employee_id.id:04d}").upper()
            code, n = base, 1
            while code in taken:
                n += 1
                code = f"{base}-{n}"
            line.login_code = code
            taken.add(code)

    @api.constrains('access_id', 'employee_id')
    def _check_employee_once_per_department(self):
        for line in self:
            twins = line.access_id.with_context(active_test=False).line_ids.filtered(
                lambda other: other.employee_id == line.employee_id)
            if len(twins) > 1:
                raise ValidationError(_(
                    "%(employee)s is already in %(department)s. Change their Role there instead of adding them again.",
                    employee=line.employee_id.name, department=line.access_id.name))

    @api.constrains('login_code')
    def _check_login_code(self):
        """A code equal to a user's login could never be used: the login page
        tries the real user first."""
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        for line in self:
            code = (line.login_code or '').lower()
            # '=ilike' treats _ and % as wildcards: confirm with an exact comparison
            if any(login.lower() == code for login in Users.search([('login', '=ilike', code)]).mapped('login')):
                raise ValidationError(_(
                    "Login code %(code)s is already the login of an Odoo user. Choose another code for %(employee)s.",
                    code=line.login_code, employee=line.employee_id.name))

    def _compute_password(self):
        self.password = False

    def _inverse_password(self):
        crypt = self.env['res.users']._crypt_context()
        for line in self.filtered('password'):
            if len(line.password) < MIN_PASSWORD_LENGTH:
                raise ValidationError(_(
                    "The password of %(employee)s must have at least %(length)s characters.",
                    employee=line.employee_id.name, length=MIN_PASSWORD_LENGTH))
            line.sudo().password_hash = crypt.hash(line.password)

    @api.depends('password_hash')
    def _compute_has_password(self):
        for line in self:
            line.has_password = bool(line.password_hash)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('login_code'):
                vals['login_code'] = vals['login_code'].strip().upper()
        lines = super().create(vals_list)
        # Employees created on the fly (e.g. "Employee 1") join the department.
        for line in lines.filtered(lambda l: not l.employee_id.department_id):
            line.employee_id.sudo().department_id = line.access_id.department_id
        return lines

    def write(self, vals):
        if vals.get('login_code'):
            vals['login_code'] = vals['login_code'].strip().upper()
        res = super().write(vals)
        if {'role', 'profile_id', 'active'} & set(vals):
            self.env.registry.clear_cache()
        return res

    def action_open_access(self):
        """Open this employee's own access; the first time it starts as a copy
        of their role's access."""
        self.ensure_one()
        if not self.profile_id:
            name = f"{self.access_id.name} - {self.employee_id.name}"
            role_profile = self.access_id._role_profile(self.role)
            self.profile_id = role_profile.copy({'name': name, 'owner_id': self.access_id.owner_id.id}) \
                if role_profile else self.env['zenvio.access.profile'].create({
                    'name': name, 'owner_id': self.access_id.owner_id.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _("Access of %s", self.employee_id.name),
            'res_model': 'zenvio.access.profile',
            'res_id': self.profile_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('zenvio_department_login.view_zenvio_access_profile_form').id, 'form')],
            'target': 'new',
        }

    def action_reset_access(self):
        """Back to the access of the employee's role."""
        profiles = self.profile_id
        self.profile_id = False
        profiles.unlink()
        return True

    @api.model
    def _zenvio_switch_origin_line(self):
        """Employee (with Can Switch) behind this session, also while they work
        as a colleague they opened, else an empty record."""
        Line = self.sudo().browse()
        if not request or not getattr(request, 'session', None) or request.session.get('zenvio_switch_origin'):
            return Line  # no session, or opened by an administrator: the administrator's rules apply
        session = request.session
        line = Line.browse(session.get('zenvio_switch_origin_line') or session.get('zenvio_dept_line_id') or 0).exists()
        if line and line.can_switch and line.active and line.access_id.active and line.employee_id.active \
                and line.access_id.owner_id.id == session.uid:
            return line
        return Line

    def _zenvio_switch_peers(self):
        """Employees this employee may open with Switch: those of the chosen
        Switch Departments (all departments of the same Top Management user
        when none are chosen)."""
        if len(self) != 1 or not self.can_switch:  # also called with no employee at all
            return self.browse()
        owner = self.access_id.owner_id
        # Read archived choices too: an archived chosen department must not
        # make the list look empty, which would mean "all departments".
        chosen = self.with_context(active_test=False).switch_access_ids
        accesses = chosen.filtered(lambda a: a.owner_id == owner) if chosen \
            else self.env['zenvio.department.access'].sudo().search([('owner_id', '=', owner.id)])
        return self.sudo().search([
            ('access_id', 'in', accesses.filtered('active').ids), ('id', '!=', self.id),
            ('employee_id.active', '=', True),
        ])

    @api.constrains('switch_access_ids', 'access_id')
    def _check_switch_departments(self):
        for line in self:
            if line.switch_access_ids.filtered(lambda a: a.owner_id != line.access_id.owner_id):
                raise ValidationError(_(
                    "%s can only switch to departments of the same Top Management user.", line.employee_id.name))

    def _zenvio_login_disabled(self):
        """'Disable Login' is ticked on the access this employee works with."""
        self.ensure_one()
        profile = self.sudo()._zenvio_profile()
        return bool(profile and profile.active and profile.disable_login)

    def _zenvio_profile(self):
        """Access profile the employee works with (may be empty: the Top Management user's rights)."""
        self.ensure_one()
        return self.profile_id or self.access_id._role_profile(self.role)

    def _verify_password(self, password):
        self.ensure_one()
        password_hash = self.sudo().password_hash
        return bool(password and password_hash) and self.env['res.users']._crypt_context().verify(password, password_hash)

    @api.model
    def _get_session_line(self):
        """Mapped employee working in the current web session, if any."""
        if not request or not getattr(request, 'session', None):
            return self.browse()
        line_id = request.session.get('zenvio_dept_line_id')
        if not line_id:
            return self.browse()
        line = self.sudo().browse(line_id).exists()
        if line.access_id.owner_id.id != self.env.uid:
            return self.browse()
        return line

    @api.model
    def _zenvio_session(self):
        """Employee and access rules of the current session, or ``None`` when
        the session is not an employee one. Computed once per request."""
        if not request or not getattr(request, 'session', None) or not request.session.get('zenvio_dept_line_id'):
            return None
        cache = getattr(request, '_zenvio_sessions', None)
        if cache is None:
            cache = request._zenvio_sessions = {}
        key = (request.session['zenvio_dept_line_id'], self.env.uid)
        if key not in cache:
            line = self._get_session_line()
            if not line:
                cache[key] = None
            else:
                profile = line._zenvio_profile()
                cache[key] = {
                    'line_id': line.id,
                    'employee_id': line.employee_id.id,
                    'department_id': line.department_id.id,
                    'rules': (profile and self.env['zenvio.access.profile']._zenvio_rules(profile.id)) or NO_RULES,
                }
        return cache[key]
