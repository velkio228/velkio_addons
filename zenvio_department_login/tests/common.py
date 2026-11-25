from odoo.tests import new_test_user


class ZenvioDepartmentCase:
    """Shared fixture: one Top Management user with PRODUCTION (manager Ana,
    user Ben) and STORES (user Cid)."""

    @classmethod
    def _zenvio_setup(cls):
        env = cls.env
        cls.top = new_test_user(env, login='zenvio_top', password='zenvio_top_pw',
                                groups='base.group_user,hr.group_hr_manager', name='Top Manager')
        cls.top.zenvio_is_ceo = True
        Department = env['hr.department']
        cls.dep_prod = Department.create({'name': 'Zenvio Production'})
        cls.dep_store = Department.create({'name': 'Zenvio Stores'})
        Employee = env['hr.employee']
        cls.ana = Employee.create({'name': 'Ana', 'department_id': cls.dep_prod.id})
        cls.ben = Employee.create({'name': 'Ben', 'department_id': cls.dep_prod.id})
        cls.cid = Employee.create({'name': 'Cid', 'department_id': cls.dep_store.id})
        Access = env['zenvio.department.access']
        cls.prod = Access.create({'owner_id': cls.top.id, 'department_id': cls.dep_prod.id})
        cls.store = Access.create({'owner_id': cls.top.id, 'department_id': cls.dep_store.id})
        Line = env['zenvio.department.employee']
        cls.line_ana = Line.create({'access_id': cls.prod.id, 'employee_id': cls.ana.id, 'role': 'manager',
                                    'login_code': 'ZANA', 'password': 'ana_pass1'})
        cls.line_ben = Line.create({'access_id': cls.prod.id, 'employee_id': cls.ben.id, 'role': 'user',
                                    'login_code': 'ZBEN', 'password': 'ben_pass1'})
        cls.line_cid = Line.create({'access_id': cls.store.id, 'employee_id': cls.cid.id, 'role': 'user',
                                    'login_code': 'ZCID', 'password': 'cid_pass1'})
        cls.employee_model = env['ir.model']._get('hr.employee')
