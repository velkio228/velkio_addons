from .test_dock import TestVelkioDock


class TestDockRegressions(TestVelkioDock):
    def make_menu(self, name, groups=None):
        action = self.env['ir.actions.client'].create({'name': name, 'tag': 'reload'})
        return self.env['ir.ui.menu'].create({
            'name': name, 'action': 'ir.actions.client,%s' % action.id,
            'group_ids': [(6, 0, groups or [])],
        })

    def test_restricted_app_cannot_be_pinned(self):
        hidden = self.make_menu('Restricted App', [self.env.ref('base.group_system').id])
        self.assertNotIn(hidden.id, self.env['ir.ui.menu'].with_user(self.user)._visible_menu_ids())
        result = self.Dock.set_dock([hidden.id])
        self.assertNotIn(hidden.id, result['menu_ids'], 'Hidden app accepted by dock RPC')

    def test_restricted_menu_cannot_be_favorited(self):
        hidden = self.make_menu('Restricted Favorite', [self.env.ref('base.group_system').id])
        self.assertNotIn(hidden.id, self.Dock.set_favorites([hidden.id]))

    def test_recent_history_ignores_restricted_apps(self):
        hidden = self.make_menu('Restricted Recent', [self.env.ref('base.group_system').id])
        self.assertFalse(self.Dock.push_recent(hidden.id))

    def test_pins_preserve_order_and_empty_configuration(self):
        first = self.make_menu('First App')
        second = self.make_menu('Second App')
        result = self.Dock.set_dock([second.id, first.id, second.id])
        self.assertEqual(result['menu_ids'], [second.id, first.id])
        result = self.Dock.set_dock([])
        self.assertTrue(result['configured'])
        self.assertEqual(result['menu_ids'], [])

    def test_new_user_starts_without_saved_pins(self):
        result = self.Dock.get_dock()
        self.assertFalse(result['configured'])
        self.assertEqual(result['menu_ids'], [])

    def test_recent_record_names_refresh_after_rename(self):
        partner = self.env['res.partner'].create({'name': 'Old record label'})
        self.Dock.push_recent_record({'model': 'res.partner', 'id': partner.id})
        partner.name = 'Updated record label'
        entries = self.Dock.get_dock()['recent_records']
        self.assertEqual(entries[0]['name'], partner.display_name)

    def test_saved_pins_hidden_after_permission_change(self):
        menu = self.make_menu('Previously visible')
        self.assertEqual(self.Dock.set_dock([menu.id])['menu_ids'], [menu.id])
        menu.group_ids = self.env.ref('base.group_system')
        self.assertEqual(self.Dock.get_dock()['menu_ids'], [])

    def test_recent_record_history_ignores_corrupt_shapes(self):
        for payload in ('null', '42', '{"model":"res.partner","id":1}',
                        '[{"model": [], "id": 1}, {"model":"res.partner","id":"bad"}]'):
            self.user.sudo().velkio_dock_recent_records = payload
            self.assertEqual(self.Dock.get_dock()['recent_records'], [])

    def test_recent_record_history_drops_deleted_records(self):
        partner = self.env['res.partner'].create({'name': 'Temporary contact'})
        self.Dock.push_recent_record({'model': 'res.partner', 'id': partner.id})
        partner.unlink()
        self.assertEqual(self.Dock.get_dock()['recent_records'], [])
