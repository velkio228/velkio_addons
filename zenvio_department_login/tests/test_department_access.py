from psycopg2 import IntegrityError

from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import ZenvioDepartmentCase


@tagged('post_install', '-at_install')
class TestDepartmentAccess(ZenvioDepartmentCase, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._zenvio_setup()

    def test_role_profiles_created_with_department(self):
        self.assertTrue(self.prod.user_profile_id and self.prod.manager_profile_id)
        self.assertEqual(self.prod.user_profile_id.owner_id, self.top)

    def test_no_extra_users_created(self):
        self.assertFalse(self.env['res.users'].search([('login', '=like', 'dept\\_%')]))

    def test_login_codes(self):
        self.assertEqual(self.line_ben.login_code, 'ZBEN')
        with self.assertRaises(ValidationError):
            self.line_ben.login_code = 'zenvio_top'  # a user's login
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.line_ben.login_code = 'ZANA'  # already used
            self.env.flush_all()

    def test_password(self):
        self.assertTrue(self.line_ben._verify_password('ben_pass1'))
        self.assertFalse(self.line_ben._verify_password('wrong'))
        with self.assertRaises(ValidationError):
            self.line_ben.password = '123'

    def test_rules_compiled(self):
        self.prod.write({
            'user_readonly': True,
            'user_model_line_ids': [(0, 0, {'model_id': self.employee_model.id, 'perm_unlink': False})],
            'user_domain_line_ids': [(0, 0, {'model_id': self.employee_model.id,
                                             'domain': "[('department_id', '=', department.id)]"})],
        })
        rules = self.env['zenvio.access.profile']._zenvio_rules(self.prod.user_profile_id.id)
        self.assertTrue(rules['readonly'])
        self.assertIn('unlink', rules['models']['hr.employee']['denied'])
        self.assertEqual(len(rules['models']['hr.employee']['domains']), 1)

    def test_read_requires_other_rights(self):
        with self.assertRaises(ValidationError):
            self.env['zenvio.access.profile.model'].create({
                'profile_id': self.prod.user_profile_id.id, 'model_id': self.employee_model.id,
                'perm_read': False, 'perm_write': True})

    def test_personal_access_starts_as_copy(self):
        self.prod.user_model_line_ids = [(0, 0, {'model_id': self.employee_model.id, 'perm_create': False})]
        self.line_ben.action_open_access()
        self.assertTrue(self.line_ben.profile_id)
        self.assertNotEqual(self.line_ben.profile_id, self.prod.user_profile_id)
        self.assertFalse(self.line_ben.profile_id.model_line_ids.perm_create)
        self.line_ben.action_reset_access()
        self.assertFalse(self.line_ben.profile_id)

    def test_portal_user_cannot_be_top_management(self):
        portal = self.env['res.users'].create({'name': 'Portal', 'login': 'zenvio_portal',
                                               'group_ids': [(6, 0, self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(UserError):
            portal.zenvio_is_ceo = True

    def test_switch_off_top_management_offers_move(self):
        with self.assertRaises(RedirectWarning):
            self.top.zenvio_is_ceo = False

    def test_move_departments(self):
        other = self.env['res.users'].create({'name': 'Other', 'login': 'zenvio_other'})
        wizard = self.env['zenvio.department.move'].with_context(default_from_user_id=self.top.id).create(
            {'to_user_id': other.id, 'remove_top_management': True})
        self.assertEqual(wizard.department_ids, self.prod | self.store)
        wizard.action_move()
        self.assertEqual(self.prod.owner_id, other)
        self.assertTrue(other.zenvio_is_ceo)
        self.assertEqual(self.prod.user_profile_id.owner_id, other)
        self.assertFalse(self.top.zenvio_is_ceo)
        self.assertTrue(self.line_ben._verify_password('ben_pass1'))

    def test_switch_peers(self):
        self.assertFalse(self.line_ben._zenvio_switch_peers())
        self.line_ben.can_switch = True
        self.assertEqual(self.line_ben._zenvio_switch_peers(), self.line_ana | self.line_cid)
        self.line_ben.switch_access_ids = self.store
        self.assertEqual(self.line_ben._zenvio_switch_peers(), self.line_cid)
        self.store.active = False  # an archived chosen department never means "all departments"
        self.assertFalse(self.line_ben._zenvio_switch_peers())
