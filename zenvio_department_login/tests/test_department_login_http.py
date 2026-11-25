import re

from odoo.tests import HttpCase, tagged

from .common import ZenvioDepartmentCase


@tagged('post_install', '-at_install')
class TestDepartmentLoginHttp(ZenvioDepartmentCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._zenvio_setup()
        cls.prod.write({
            'user_model_line_ids': [(0, 0, {'model_id': cls.employee_model.id, 'perm_unlink': False})],
            'user_domain_line_ids': [(0, 0, {'model_id': cls.employee_model.id,
                                             'domain': "[('department_id', '=', department.id)]"})],
        })

    def _employee_login(self, code, password):
        self.authenticate(None, None)
        page = self.url_open('/web/department/login').text
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.url_open('/web/department/login', allow_redirects=False,
                             data={'login_code': code, 'password': password, 'csrf_token': token})

    def _info(self):
        return self.make_jsonrpc_request('/web/session/get_session_info')

    def test_employee_login_and_rules(self):
        response = self._employee_login('zben', 'ben_pass1')
        self.assertEqual(response.status_code, 303)
        info = self._info()
        self.assertEqual(info['uid'], self.top.id)
        self.assertEqual(info['zenvio_department']['employee'], 'Ben')
        visible = self.make_jsonrpc_request('/web/dataset/call_kw/hr.employee/search', {
            'model': 'hr.employee', 'method': 'search', 'args': [[]], 'kwargs': {}})
        self.assertEqual(set(visible), set((self.ana | self.ben).ids))
        can_delete = self.make_jsonrpc_request('/web/dataset/call_kw/hr.employee/has_access', {
            'model': 'hr.employee', 'method': 'has_access', 'args': [[], 'unlink'], 'kwargs': {}})
        self.assertFalse(can_delete)

    def test_wrong_password_and_lock(self):
        for _attempt in range(5):
            self.assertEqual(self._employee_login('ZBEN', 'wrong').status_code, 200)
        response = self._employee_login('ZBEN', 'ben_pass1')
        self.assertIn('Too many failed attempts', response.text)
        # other employees and the Top Management user are not locked
        self.assertEqual(self._employee_login('ZANA', 'ana_pass1').status_code, 303)

    def test_disable_login(self):
        self.prod.user_disable_login = True
        response = self._employee_login('ZBEN', 'ben_pass1')
        self.assertIn('Login is disabled', response.text)

    def test_lock_applies_before_disabled_check(self):
        """A locked code must not reveal a correct password through the 'disabled' message."""
        self.prod.user_disable_login = True
        for _attempt in range(5):
            self._employee_login('ZBEN', 'wrong')
        response = self._employee_login('ZBEN', 'ben_pass1')
        self.assertIn('Too many failed attempts', response.text)
        self.assertNotIn('Login is disabled', response.text)

    def test_admin_switch_and_back(self):
        self.authenticate('admin', 'admin')
        result = self.make_jsonrpc_request(f'/web/department/switch/{self.line_ben.id}')
        self.assertEqual(result['url'], '/odoo')
        info = self._info()
        self.assertEqual(info['zenvio_department']['employee'], 'Ben')
        self.assertTrue(info['zenvio_department']['switched_from'])
        self.make_jsonrpc_request('/web/department/switch/back')
        info = self._info()
        self.assertEqual(info['uid'], self.env.ref('base.user_admin').id)
        self.assertNotIn('zenvio_department', info)

    def test_employee_cannot_switch_without_permission(self):
        self._employee_login('ZBEN', 'ben_pass1')
        self.assertEqual(self.make_jsonrpc_request('/web/department/switch/targets'), [])
        self.line_ben.can_switch = True
        targets = self.make_jsonrpc_request('/web/department/switch/targets')
        codes = {e['code'] for dept in targets for e in dept['employees']}
        self.assertEqual(codes, {'ZANA', 'ZCID'})
