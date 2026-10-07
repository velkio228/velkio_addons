from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVelkioDock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.user = cls.Users.create({
            "name": "Velkio Dock Test User",
            "login": "velkio_dock_test_user",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.Dock = cls.env["velkio.dock.item"].with_user(cls.user)

    def test_settings_are_clamped_and_validated(self):
        settings = self.Dock.set_settings({
            "recent_limit": 999,
            "accent_color": "not-a-colour",
            "position": "invalid",
            "autohide": True,
        })
        self.assertEqual(settings["recent_limit"], 15)
        self.assertTrue(settings["autohide"])
        self.assertNotEqual(settings["accent_color"], "not-a-colour")
        self.assertNotEqual(settings["position"], "invalid")

    def test_recent_record_rejects_unknown_model(self):
        self.assertFalse(self.Dock.push_recent_record({"model": "x.missing.model", "id": 1, "name": "Fake"}))

    def test_recent_record_uses_server_display_name(self):
        partner = self.env["res.partner"].create({"name": "Server Truth"})
        result = self.Dock.push_recent_record({
            "model": "res.partner", "id": partner.id, "name": "Client Spoof"
        })
        self.assertTrue(result)
        self.assertEqual(result["name"], partner.display_name)
        self.assertNotEqual(result["name"], "Client Spoof")

    def test_dock_items_are_isolated_per_user(self):
        other = self.Users.create({
            "name": "Velkio Dock Other User",
            "login": "velkio_dock_other_user",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        root = self.env["ir.ui.menu"].create({"name": "Velkio Test Root"})
        item = self.env["velkio.dock.item"].create({"user_id": other.id, "menu_id": root.id})
        self.assertFalse(self.env["velkio.dock.item"].with_user(self.user).search([("id", "=", item.id)]))
