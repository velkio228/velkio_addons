from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, AccessError, RedirectWarning, UserError
from odoo.http import request

CEO_GROUP = 'zenvio_department_login.group_department_manager'

# Fields an employee logged in through a department must never change.
PROTECTED_USER_FIELDS = {'password', 'login', 'group_ids', 'active', 'zenvio_is_ceo', 'zenvio_owned_department_ids'}


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Set on the hidden logins that versions 19.0.5.x created (archived by 19.0.7).
    zenvio_department_login = fields.Boolean(
        string='Hidden Department Login', readonly=True, copy=False,
        help="Hidden login of a department role (User / Manager). Employees log in to it with their own code.")
    zenvio_is_ceo = fields.Boolean(
        string='Top Management', compute='_compute_zenvio_is_ceo', inverse='_inverse_zenvio_is_ceo',
        help="This user can access and manage multiple departments: employees of its departments sign in "
             "with their own code and password and work through this user.")
    zenvio_owned_department_ids = fields.One2many(
        'zenvio.department.access', 'owner_id', string='Department')

    @api.depends('group_ids')
    def _compute_zenvio_is_ceo(self):
        group = self.env.ref(CEO_GROUP)
        for user in self:
            user.zenvio_is_ceo = group in user.group_ids

    def _inverse_zenvio_is_ceo(self):
        group = self.env.ref(CEO_GROUP)
        for user in self:
            if user.zenvio_is_ceo and user.share:
                raise UserError(_("%s is not an internal user and cannot be Top Management.", user.name))
            if user.zenvio_is_ceo and group not in user.group_ids:
                user.group_ids = [(4, group.id)]
            elif not user.zenvio_is_ceo and group in user.group_ids:
                if user.with_context(active_test=False).zenvio_owned_department_ids:
                    raise RedirectWarning(
                        _("%s still has departments. Move them to another Top Management user first "
                          "(their employees and access move with them), or delete them.", user.name),
                        user._zenvio_move_action(remove_top_management=True),
                        _("Move Departments"),
                    )
                user.group_ids = [(3, group.id)]

    def action_zenvio_add_department(self):
        """Open a new department of this Top Management user in a dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Add Department"),
            'res_model': 'zenvio.department.access',
            'view_mode': 'form',
            'views': [(self.env.ref('zenvio_department_login.view_zenvio_department_access_form').id, 'form')],
            'context': {'default_owner_id': self.id, 'zenvio_from_user': True},
            'target': 'new',
        }

    def _zenvio_move_action(self, remove_top_management=False):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('zenvio_department_login.action_zenvio_department_move')
        action['context'] = {'default_from_user_id': self.id, 'zenvio_remove_top_management': remove_top_management}
        return action

    def action_zenvio_move_departments(self):
        """Move this user's departments to another Top Management user."""
        return self._zenvio_move_action()

    def write(self, vals):
        if _in_employee_session() and (
                'password' in vals  # also in sudo: change_password() writes it as superuser
                or (PROTECTED_USER_FIELDS & set(vals) and not self.env.su)):
            raise AccessError(_("Employees logged in through a department cannot change users or passwords."))
        return super().write(vals)

    @api.model
    def change_password(self, old_passwd, new_passwd):
        if _in_employee_session():
            raise AccessError(_("Employees logged in through a department cannot change users or passwords."))
        return super().change_password(old_passwd, new_passwd)

    def preference_change_password(self):
        if _in_employee_session():
            raise AccessError(_("Employees logged in through a department cannot change users or passwords."))
        return super().preference_change_password()

    def _check_credentials(self, credential, env):
        """Add the ``department_password`` login type: an employee's own
        password logs them in as the Top Management user of their department, narrowed by
        their access profile. Hidden logins of older versions can never be
        used with a password."""
        if credential.get('type') != 'department_password':
            if credential.get('type') == 'password' and self.env.user.sudo().zenvio_department_login:
                raise AccessDenied(_("This is a department login. Please log in with your employee code."))
            return super()._check_credentials(credential, env)

        line = self.env['zenvio.department.employee'].sudo().browse(int(credential.get('line_id') or 0)).exists()
        if (
            not line
            or not line.active
            or not line.access_id.active
            or not line.employee_id.active
            or line._zenvio_login_disabled()
            or line.access_id.owner_id != self.env.user
            or not line._verify_password(credential.get('password') or '')
        ):
            raise AccessDenied()
        return {'uid': self.env.user.id, 'auth_method': 'department_password', 'mfa': 'skip'}


def _in_employee_session():
    return bool(request and getattr(request, 'session', None) and request.session.get('zenvio_dept_line_id'))
