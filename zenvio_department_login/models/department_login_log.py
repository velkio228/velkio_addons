from odoo import fields, models


class ZenvioDepartmentLoginLog(models.Model):
    _name = 'zenvio.department.login.log'
    _description = 'Department Access Login Log'
    _order = 'login_date desc, id desc'

    access_id = fields.Many2one('zenvio.department.access', string='Department', ondelete='cascade', index=True)
    department_id = fields.Many2one(related='access_id.department_id', store=True, string='HR Department')
    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='set null')
    login_code = fields.Char()
    login_date = fields.Datetime(string='Login Time', default=fields.Datetime.now, required=True)
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char()
    result = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Wrong code or password'),
        ('switch', 'Switched by administrator'),
    ], required=True, default='success')
    switched_by_employee_id = fields.Many2one(
        'hr.employee', string='Switched By Employee', readonly=True,
        help="Employee (with Can Switch) who opened this colleague's session.")
    switched_by_id = fields.Many2one('res.users', string='Switched By', readonly=True,
                                     help="Administrator or Top Management user who opened this employee's session.")
