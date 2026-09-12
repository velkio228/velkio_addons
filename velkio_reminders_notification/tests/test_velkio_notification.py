# -*- coding: utf-8 -*-
import json
from datetime import timedelta

import odoo.tests
from odoo import fields
from odoo.exceptions import AccessError, ValidationError


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioNotification(odoo.tests.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = cls.env['res.users'].create({
            'name': 'Reader', 'login': 'velkio_reader', 'email': 'reader@example.com',
        })
        cls.other = cls.env['res.users'].create({
            'name': 'Other', 'login': 'velkio_other', 'email': 'other@example.com',
        })

    def _notice(self, **kw):
        values = {
            'name': 'Heads up',
            'body': '<p>Something <strong>important</strong>.</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=5),
            'audience': 'users',
            'user_ids': [(6, 0, [self.reader.id])],
            'state': 'scheduled',
        }
        values.update(kw)
        return self.env['velkio.notification'].create(values)

    # ── delivery ──────────────────────────────────────────────

    def test_dispatch_creates_one_row_per_person(self):
        notice = self._notice(user_ids=[(6, 0, [self.reader.id, self.other.id])])
        notice._dispatch()
        self.assertEqual(notice.state, 'sent')
        self.assertEqual(notice.recipient_count, 2)
        self.assertEqual(notice.open_count, 2)
        self.assertEqual(set(notice.recipient_ids.mapped('state')), {'sent'})

    def test_cron_sends_only_what_is_due(self):
        future = self._notice(notify_datetime=fields.Datetime.now() + timedelta(hours=2))
        due = self._notice(notify_datetime=fields.Datetime.now() - timedelta(minutes=1))
        self.env['velkio.notification']._cron_dispatch()
        self.assertEqual(future.state, 'scheduled', 'A future notice must wait.')
        self.assertEqual(due.state, 'sent', 'A due notice must go out.')

    def test_popup_goes_to_the_account_channel(self):
        """The bus target is the partner, which every device of the user joins."""
        notice = self._notice()
        notice._dispatch()
        self.env.cr.precommit.run()  # trigger the creation of bus.bus records
        partners = []
        for row in self.env['bus.bus'].search([]):
            if 'velkio_notification' not in (row.message or ''):
                continue
            channel = json.loads(row.channel)
            if isinstance(channel, list) and len(channel) == 3 and channel[1] == 'res.partner':
                partners.append(channel[2])
        self.assertIn(self.reader.partner_id.id, partners)

    def test_muted_reader_is_recorded_but_not_pushed(self):
        self.reader.velkio_popup_enabled = False
        notice = self._notice()
        notice._dispatch()
        self.assertEqual(notice.recipient_ids.state, 'muted')
        self.assertEqual(notice.open_count, 0)

    def test_urgent_ignores_the_mute(self):
        self.reader.velkio_popup_enabled = False
        notice = self._notice(level='urgent')
        notice._dispatch()
        self.assertEqual(notice.recipient_ids.state, 'sent')

    def test_snooze_comes_back_when_time_is_up(self):
        notice = self._notice()
        notice._dispatch()
        row = notice.recipient_ids
        row.write({
            'state': 'snoozed',
            'snooze_until': fields.Datetime.now() - timedelta(minutes=1),
        })
        self.env['velkio.notification.recipient']._cron_wake_snoozed()
        self.assertEqual(row.state, 'sent')

    # ── permissions ───────────────────────────────────────────

    def test_a_plain_user_can_remind_themselves(self):
        notice = self.env['velkio.notification'].with_user(self.reader).create({
            'name': 'Call the supplier',
            'body': '<p>At 3pm</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me',
        })
        notice._dispatch()
        self.assertEqual(notice.recipient_ids.user_id, self.reader)

    def test_a_plain_user_cannot_notify_someone_else(self):
        with self.assertRaises(ValidationError):
            self.env['velkio.notification'].with_user(self.reader).create({
                'name': 'Not allowed',
                'body': '<p>x</p>',
                'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
                'audience': 'users',
                'user_ids': [(6, 0, [self.other.id])],
            })

    def test_a_plain_user_cannot_notify_everybody(self):
        with self.assertRaises(ValidationError):
            self.env['velkio.notification'].with_user(self.reader).create({
                'name': 'Not allowed',
                'body': '<p>x</p>',
                'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
                'audience': 'all',
            })

    def test_people_do_not_see_each_others_notices(self):
        notice = self._notice()
        notice._dispatch()
        visible = self.env['velkio.notification'].with_user(self.other).search([])
        self.assertNotIn(notice.id, visible.ids)
        visible_to_reader = self.env['velkio.notification'].with_user(self.reader).search([])
        self.assertIn(notice.id, visible_to_reader.ids)

    def test_recipient_rows_are_private(self):
        notice = self._notice()
        notice._dispatch()
        rows = self.env['velkio.notification.recipient'].with_user(self.other).search([])
        self.assertFalse(rows.filtered(lambda r: r.user_id != self.other))

    # ── scaling ───────────────────────────────────────────────

    def test_dispatch_does_not_scale_per_person(self):
        """Notifying everybody must not cost a query per person."""
        def cost(count):
            users = self.env['res.users'].create([{
                'name': 'Bulk %s' % i,
                'login': 'velkio_bulk_%s_%s' % (count, i),
                'email': 'vb%s_%s@example.com' % (count, i),
            } for i in range(count)])
            notice = self._notice(user_ids=[(6, 0, users.ids)])
            self.env.flush_all()
            before = self.env.cr.sql_log_count
            notice._dispatch()
            self.env.flush_all()
            return self.env.cr.sql_log_count - before

        small, big = cost(5), cost(40)
        self.assertLess(
            big, small * 2,
            'Dispatch is scaling per person: %s queries for 5, %s for 40.' % (small, big),
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioEndpoints(odoo.tests.HttpCase):
    """The routes the popup calls, including the multi-device behaviour."""

    def setUp(self):
        super().setUp()
        self.reader = self.env['res.users'].create({
            'name': 'Reader', 'login': 'velkio_http', 'password': 'velkio_http_pwd',
            'email': 'http@example.com',
        })
        self.notice = self.env['velkio.notification'].create({
            'name': 'On every screen',
            'body': '<p>Please read this.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users',
            'user_ids': [(6, 0, [self.reader.id])],
            'require_ack': True,
            'state': 'scheduled',
        })
        self.notice._dispatch()

    def _call(self, route, params=None):
        return self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params or {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

    def test_a_device_opening_later_still_gets_it(self):
        self.authenticate('velkio_http', 'velkio_http_pwd')
        result = self._call('/velkio/notification/pending')
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['popups']), 1)
        self.assertEqual(result['popups'][0]['id'], self.notice.id)
        self.assertTrue(result['popups'][0]['require_ack'])

    def test_answering_closes_it_on_the_other_devices(self):
        self.env['bus.bus'].search([]).unlink()
        self.authenticate('velkio_http', 'velkio_http_pwd')
        result = self._call(
            '/velkio/notification/done',
            {'notification_id': self.notice.id, 'acknowledged': True},
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 0)

        row = self.notice.recipient_ids
        self.assertEqual(row.state, 'done')
        self.assertTrue(row.acknowledged)

        closes = self.env['bus.bus'].search([])
        self.assertTrue(
            any('velkio_notification_close' in (n.message or '') for n in closes),
            'Answering must tell the other devices to close the popup.',
        )
        self.assertEqual(self._call('/velkio/notification/pending')['popups'], [])

    def test_snooze_hides_it_until_later(self):
        self.authenticate('velkio_http', 'velkio_http_pwd')
        self._call(
            '/velkio/notification/snooze',
            {'notification_id': self.notice.id, 'minutes': 30},
        )
        row = self.notice.recipient_ids
        self.assertEqual(row.state, 'snoozed')
        self.assertEqual(row.snooze_count, 1)
        self.assertEqual(self._call('/velkio/notification/pending')['popups'], [])


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioUI(odoo.tests.HttpCase):
    """The web client must boot with these assets, and actually show a popup."""

    def test_three_at_once_show_one_card_and_a_waiting_chip(self):
        """Exactly the screenshot: three notices land together.

        Only one card may be on screen; the other two wait behind the chip so
        the stack cannot run off the bottom of the window.
        """
        admin = self.env.ref('base.user_admin')
        for title, level in [('Month-end close today', 'urgent'),
                             ('Submit your expenses', 'warning'),
                             ('Stand-up moved to 10:30', 'info')]:
            notice = self.env['velkio.notification'].create({
                'name': title, 'body': '<p>%s</p>' % title,
                'notify_datetime': fields.Datetime.now(),
                'audience': 'users', 'user_ids': [(6, 0, [admin.id])],
                'level': level, 'duration': 0, 'state': 'scheduled',
            })
            notice._dispatch()

        self.browser_js(
            '/web',
            """
            (async () => {
                const find = async (sel) => {
                    for (let i = 0; i < 80; i++) {
                        const el = document.querySelector(sel);
                        if (el) return el;
                        await new Promise((r) => setTimeout(r, 250));
                    }
                    throw new Error('never appeared: ' + sel);
                };
                await find('.velkio-popup');
                // Give any others their chance to pile on.
                await new Promise((r) => setTimeout(r, 1500));

                const cards = document.querySelectorAll('.velkio-popup');
                if (cards.length !== 1) {
                    throw new Error(cards.length + ' cards on screen, expected 1');
                }
                // The most urgent one is the one that gets the slot.
                const title = cards[0].querySelector('.velkio-title').textContent;
                if (!title.includes('Month-end close today')) {
                    throw new Error('expected the urgent notice, got: ' + title);
                }
                const chip = await find('.velkio-more');
                if (!chip.textContent.includes('2')) {
                    throw new Error('chip should count 2, says: ' + chip.textContent);
                }
                // Nothing may hang below the bottom of the window.
                const box = document.querySelector('.velkio-layer')
                    .getBoundingClientRect();
                if (box.bottom > window.innerHeight + 1) {
                    throw new Error('the stack runs off the screen');
                }
                console.log('test successful');
            })();
            """,
            "odoo.isReady === true",
            login='admin',
            timeout=180,
        )

    def test_close_all_clears_the_screen_but_keeps_the_count(self):
        """The button empties the view without reading anything."""
        admin = self.env.ref('base.user_admin')
        for title in ('One', 'Two', 'Three'):
            notice = self.env['velkio.notification'].create({
                'name': title, 'body': '<p>%s</p>' % title,
                'notify_datetime': fields.Datetime.now(),
                'audience': 'users', 'user_ids': [(6, 0, [admin.id])],
                'duration': 0, 'state': 'scheduled',
            })
            notice._dispatch()

        self.browser_js(
            '/web',
            """
            (async () => {
                const find = async (sel) => {
                    for (let i = 0; i < 80; i++) {
                        const el = document.querySelector(sel);
                        if (el) return el;
                        await new Promise((r) => setTimeout(r, 250));
                    }
                    throw new Error('never appeared: ' + sel);
                };
                const gone = async (sel) => {
                    for (let i = 0; i < 80; i++) {
                        if (!document.querySelector(sel)) return;
                        await new Promise((r) => setTimeout(r, 250));
                    }
                    throw new Error('still there: ' + sel);
                };
                await find('.velkio-popup');
                await find('.velkio-more');
                const badge = await find('.velkio-systray-badge');
                const before = badge.textContent.trim();
                if (before !== '3') {
                    throw new Error('bell should start at 3, says ' + before);
                }

                (await find('.velkio-clear')).click();
                await gone('.velkio-popup');
                await gone('.velkio-more');

                await new Promise((r) => setTimeout(r, 800));
                const after = document.querySelector('.velkio-systray-badge');
                if (!after || after.textContent.trim() !== '3') {
                    throw new Error('the bell must still say 3, says: '
                        + (after ? after.textContent.trim() : 'nothing'));
                }
                console.log('test successful');
            })();
            """,
            "odoo.isReady === true",
            login='admin',
            timeout=180,
        )

        rows = self.env['velkio.notification.recipient'].search(
            [('user_id', '=', admin.id)])
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            set(rows.mapped('state')), {'seen'},
            'Cleared from the screen, not answered.',
        )
        self.assertFalse(
            any(rows.mapped('read_at')), 'And still unread.',
        )

    def test_a_reader_sees_the_content_and_none_of_the_authoring(self):
        """Someone who did not write it has no use for the settings.

        The form keeps what a reader came for — what it says, when it is due,
        how urgent — and drops the workflow bar, the delivery figures, the
        audience picker and the popup settings.
        """
        Users = self.env['res.users']
        author = Users.create({
            'name': 'Priya', 'login': 'rv_author', 'password': 'rv_author',
            'email': 'priya@example.com',
            'groups_id': [(4, self.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })
        reader = Users.create({
            'name': 'Ashwin', 'login': 'rv_reader', 'password': 'rv_reader',
            'email': 'ashwin@example.com',
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        notice = self.env['velkio.notification'].with_user(author).create({
            'name': 'Server maintenance at 6 PM',
            'body': '<p>Please <strong>save your work</strong>.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, [reader.id])],
            'duration': 30, 'state': 'scheduled',
        })
        notice._dispatch()
        # Snoozed, so no popup covers the form we are inspecting.
        self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', notice.id),
        ]).write({'state': 'snoozed',
                  'snooze_until': fields.Datetime.now() + timedelta(hours=1)})
        action = self.env.ref(
            'velkio_reminders_notification.action_velkio_my_notifications')

        self.browser_js(
            '/web#id=%s&action=%s&model=velkio.notification&view_type=form'
            % (notice.id, action.id),
            """
            (async () => {
                const find = async (sel) => {
                    for (let i = 0; i < 80; i++) {
                        const el = document.querySelector(sel);
                        if (el) return el;
                        await new Promise((r) => setTimeout(r, 250));
                    }
                    throw new Error('never appeared: ' + sel);
                };
                await find('.o_form_view .velkio-message-field');
                for (const sel of ['[name="name"]', '[name="notify_datetime"]',
                                   '[name="level"]']) {
                    await find('.o_form_view ' + sel);
                }
                const gone = {
                    'workflow bar': '.o_form_view .o_statusbar_status',
                    'delivery figures': '.o_form_view .oe_stat_button',
                    'audience picker': '.o_form_view [name="audience"]',
                    'template picker': '.o_form_view [name="template_id"]',
                    'auto-close': '.o_form_view [name="duration"]',
                    'acknowledgement': '.o_form_view [name="require_ack"]',
                    'popup style': '.o_form_view [name="style_id"]',
                };
                for (const [label, sel] of Object.entries(gone)) {
                    if (document.querySelector(sel)) {
                        throw new Error('a reader should not see the ' + label);
                    }
                }
                console.log('test successful');
            })();
            """,
            "odoo.isReady === true",
            login='rv_reader',
            timeout=180,
        )

    def test_the_eye_marks_a_notice_read_from_the_list(self):
        """Clicking the eye in the list must actually write it through."""
        admin = self.env.ref('base.user_admin')
        notice = self.env['velkio.notification'].create({
            'name': 'Submit your expenses',
            'body': '<p>Before Friday, please.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, [admin.id])],
            'duration': 0, 'state': 'scheduled',
        })
        notice._dispatch()
        # Snoozed, so no popup lands on top of the row we are about to click.
        self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', notice.id),
        ]).write({'state': 'snoozed',
                  'snooze_until': fields.Datetime.now() + timedelta(hours=1)})
        action = self.env.ref(
            'velkio_reminders_notification.action_velkio_my_notifications')

        self.browser_js(
            '/web#action=%s&model=velkio.notification&view_type=list' % action.id,
            """
            (async () => {
                const find = async (sel) => {
                    for (let i = 0; i < 80; i++) {
                        const el = document.querySelector(sel);
                        if (el) return el;
                        await new Promise((r) => setTimeout(r, 250));
                    }
                    throw new Error('never appeared: ' + sel);
                };
                const eye = await find('.o_data_row .velkio-eye');
                if (eye.classList.contains('velkio-eye-read')) {
                    throw new Error('it should start unread');
                }
                if (!eye.querySelector('.fa-eye-slash')) {
                    throw new Error('unread should show a closed eye');
                }
                eye.click();
                await find('.o_data_row .velkio-eye.velkio-eye-read');
                if (!document.querySelector('.velkio-eye-read .fa-eye')) {
                    throw new Error('read should show an open eye');
                }
                console.log('test successful');
            })();
            """,
            "odoo.isReady === true",
            login='admin',
            timeout=180,
        )

        notice.invalidate_recordset()
        row = self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', notice.id), ('user_id', '=', admin.id)])
        self.assertTrue(
            row.read_at,
            'Clicking the eye has to reach the database, not just the screen.',
        )

    def test_webclient_boots(self):
        self.browser_js(
            '/web',
            "console.log('test successful');",
            "odoo.isReady === true",
            login='admin',
            timeout=120,
        )

    def test_popup_appears_over_the_current_screen(self):
        admin = self.env.ref('base.user_admin')
        notice = self.env['velkio.notification'].create({
            'name': 'Stand-up in 5 minutes',
            'body': '<p>Join the <strong>daily call</strong>.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users',
            'user_ids': [(6, 0, [admin.id])],
            'duration': 0,
            'require_ack': True,
            'state': 'scheduled',
        })
        notice._dispatch()
        self.browser_js(
            '/web',
            """
            (async () => {
                for (let i = 0; i < 60; i++) {
                    const card = document.querySelector('.velkio-popup');
                    if (card) {
                        if (!card.querySelector('.velkio-body strong')) {
                            throw new Error('message was escaped instead of rendered');
                        }
                        if (!card.querySelector('.velkio-btn-primary')) {
                            throw new Error('acknowledge button missing');
                        }
                        if (!card.querySelector('.velkio-bell')) {
                            throw new Error('bell missing from the reminder card');
                        }
                        console.log('test successful');
                        return;
                    }
                    await new Promise((r) => setTimeout(r, 250));
                }
                throw new Error('popup never appeared');
            })();
            """,
            "odoo.isReady === true",
            login='admin',
            timeout=120,
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioOwnRowAccess(odoo.tests.TransactionCase):
    """People must be able to act on their own notifications.

    The recipient table is read-only for ordinary users, so anything that
    writes to it on their behalf has to go through sudo with an ownership
    check. These two paths both broke on that.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env['res.users'].create({
            'name': 'Staff', 'login': 'velkio_own', 'email': 'own@example.com',
        })

    def _own_note(self):
        note = self.env['velkio.notification'].with_user(self.staff).create({
            'name': 'Call back',
            'body': '<p>later</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=10),
            'audience': 'me',
        })
        note._dispatch()
        return note

    def test_a_user_can_close_their_own_notification(self):
        note = self._own_note()
        note.recipient_ids.with_user(self.staff).action_mark_done()
        self.assertEqual(note.recipient_ids.state, 'done')

    def test_a_user_cannot_close_someone_elses(self):
        other = self.env['res.users'].create({
            'name': 'Other', 'login': 'velkio_own_other', 'email': 'oo@example.com',
        })
        note = self._own_note()
        with self.assertRaises(AccessError):
            note.recipient_ids.with_user(other).action_mark_done()

    def test_the_author_can_send_the_same_notice_twice(self):
        """Re-dispatching updates the existing rows instead of failing."""
        note = self._own_note()
        note.with_user(self.staff).action_send_now()
        self.assertEqual(note.recipient_count, 1, 'No duplicate recipient row.')
        self.assertEqual(note.recipient_ids.state, 'sent')


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioExactTiming(odoo.tests.HttpCase):
    """The popup must land on the exact second, not on the next cron tick."""

    def setUp(self):
        super().setUp()
        self.reader = self.env['res.users'].create({
            'name': 'Timed', 'login': 'velkio_timed', 'password': 'velkio_timed_pwd',
            'email': 'timed@example.com',
        })

    def _call(self, route, params=None):
        return self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params or {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

    def _notice(self, seconds_ahead, **kw):
        values = {
            'name': 'Exactly on time',
            'body': '<p>now</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(seconds=seconds_ahead),
            'audience': 'users',
            'user_ids': [(6, 0, [self.reader.id])],
            'state': 'scheduled',
        }
        values.update(kw)
        return self.env['velkio.notification'].create(values)

    def test_the_browser_is_told_how_long_is_left(self):
        notice = self._notice(90)
        self.authenticate('velkio_timed', 'velkio_timed_pwd')
        upcoming = self._call('/velkio/notification/pending')['upcoming']
        entry = next((u for u in upcoming if u['id'] == notice.id), None)
        self.assertIsNotNone(entry, 'A notice due soon must be announced to the browser.')
        # Sent as a countdown, so a browser with a wrong clock is unaffected.
        self.assertGreater(entry['delay_ms'], 80000)
        self.assertLessEqual(entry['delay_ms'], 90000)

    def test_a_far_off_notice_is_not_armed_yet(self):
        far = self._notice(60 * 60 * 5)
        self.authenticate('velkio_timed', 'velkio_timed_pwd')
        upcoming = self._call('/velkio/notification/pending')['upcoming']
        self.assertNotIn(far.id, [u['id'] for u in upcoming])

    def test_firing_on_time_shows_it_and_records_the_delivery(self):
        notice = self._notice(-1)  # a second overdue
        self.authenticate('velkio_timed', 'velkio_timed_pwd')
        result = self._call(
            '/velkio/notification/fire', {'notification_id': notice.id})
        self.assertTrue(result['ok'])
        self.assertEqual(result['popup']['id'], notice.id)
        # The row is written even though the cron has not run yet, so the
        # reader can answer straight away.
        row = notice.recipient_ids
        self.assertEqual(len(row), 1)
        self.assertEqual(row.user_id, self.reader)
        self.assertEqual(row.state, 'sent')

    def test_firing_early_is_refused(self):
        notice = self._notice(120)
        self.authenticate('velkio_timed', 'velkio_timed_pwd')
        result = self._call(
            '/velkio/notification/fire', {'notification_id': notice.id})
        self.assertFalse(result['ok'], 'A notice that is not due yet must not be shown.')
        self.assertFalse(notice.recipient_ids)

    def test_a_cancelled_notice_never_appears(self):
        notice = self._notice(-1)
        notice.action_cancel()
        self.authenticate('velkio_timed', 'velkio_timed_pwd')
        result = self._call(
            '/velkio/notification/fire', {'notification_id': notice.id})
        self.assertFalse(result['ok'])

    def test_someone_else_cannot_fire_my_notice(self):
        notice = self._notice(-1)
        intruder = self.env['res.users'].create({
            'name': 'Intruder', 'login': 'velkio_intruder',
            'password': 'velkio_intruder_pwd', 'email': 'in@example.com',
        })
        self.authenticate('velkio_intruder', 'velkio_intruder_pwd')
        result = self._call(
            '/velkio/notification/fire', {'notification_id': notice.id})
        self.assertFalse(result['ok'])
        self.assertFalse(notice.recipient_ids.filtered(lambda r: r.user_id == intruder))

    def test_scheduling_wakes_the_cron_at_that_moment(self):
        """A trigger is registered so the server does not wait for the next tick."""
        cron = self.env.ref('velkio_reminders_notification.ir_cron_velkio_dispatch')
        before = self.env['ir.cron.trigger'].search_count([('cron_id', '=', cron.id)])
        notice = self._notice(90)
        after = self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id)])
        self.assertGreater(len(after), before)
        self.assertIn(
            notice.notify_datetime, after.mapped('call_at'),
            'The scheduler must be woken at the moment the notice is due.',
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioStyleAndTemplates(odoo.tests.TransactionCase):
    """The configurable look, and the ready-made library."""

    def test_a_default_style_ships_with_the_module(self):
        style = self.env['velkio.popup.style'].get_default_style()
        self.assertTrue(style, 'A default style must exist out of the box.')
        payload = style._as_payload()
        for key in ('position', 'width', 'appearance', 'surface', 'radius',
                    'shadow', 'animation', 'colors', 'stack_limit'):
            self.assertIn(key, payload, 'The browser needs %s to paint the popup.' % key)

    def test_only_one_style_can_be_the_default(self):
        Style = self.env['velkio.popup.style']
        first = Style.get_default_style()
        second = Style.create({'name': 'Another', 'is_default': True})
        first.invalidate_recordset()
        self.assertFalse(first.is_default, 'Setting a new default clears the old one.')
        self.assertTrue(second.is_default)

    def test_a_notification_can_override_the_style(self):
        dark = self.env['velkio.popup.style'].create({
            'name': 'Dark test', 'appearance': 'dark', 'position': 'bottom-left',
        })
        notice = self.env['velkio.notification'].create({
            'name': 'Styled', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=5),
            'audience': 'me', 'style_id': dark.id,
        })
        payload = notice._payload(self.env.user)
        self.assertEqual(payload['style']['appearance'], 'dark')
        self.assertEqual(payload['style']['position'], 'bottom-left')

    def test_colours_must_be_hex(self):
        with self.assertRaises(ValidationError):
            self.env['velkio.popup.style'].create({
                'name': 'Bad colour', 'accent_color': 'not-a-colour',
            })

    def test_the_template_library_is_installed(self):
        Template = self.env['velkio.template']
        templates = Template.search([])
        self.assertGreaterEqual(len(templates), 30, 'Ships with a usable library.')
        # Compare against the model rather than a hard-coded number, so adding
        # a category makes this fail loudly until the library covers it.
        declared = {key for key, _label in Template._fields['category'].selection}
        self.assertEqual(
            set(templates.mapped('category')), declared,
            'Every category offered in the form should have templates in it.',
        )

    def test_a_template_fills_in_a_notification(self):
        template = self.env.ref('velkio_reminders_notification.tpl_maintenance')
        notice = self.env['velkio.notification'].new({'template_id': template.id})
        notice._onchange_template()
        self.assertEqual(notice.name, template.title)
        self.assertEqual(notice.level, 'urgent')
        self.assertTrue(notice.require_ack)
        self.assertGreater(notice.notify_datetime, fields.Datetime.now())


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioDashboard(odoo.tests.TransactionCase):
    """The dashboard buckets must count what they say they count."""

    def test_every_bucket_is_present(self):
        data = self.env['velkio.notification'].get_dashboard_data()
        self.assertEqual(
            [b['key'] for b in data['buckets']],
            ['today', 'scheduled', 'assigned', 'flagged', 'urgent', 'completed', 'all'],
        )

    def test_counts_match_the_domain_the_tile_opens(self):
        Notification = self.env['velkio.notification']
        Notification.create({
            'name': 'Flagged one', 'body': '<p>x</p>', 'flagged': True, 'level': 'urgent',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me', 'state': 'scheduled',
        })
        for bucket in Notification.get_dashboard_data()['buckets']:
            self.assertEqual(
                bucket['count'], Notification.search_count(bucket['domain']),
                'Bucket "%s" shows a number the list does not match.' % bucket['key'],
            )

    def test_flagging_moves_it_into_the_flagged_bucket(self):
        Notification = self.env['velkio.notification']
        before = next(
            b['count'] for b in Notification.get_dashboard_data()['buckets']
            if b['key'] == 'flagged'
        )
        notice = Notification.create({
            'name': 'Star me', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me',
        })
        notice.action_toggle_flag()
        self.assertTrue(notice.flagged)
        after = next(
            b['count'] for b in Notification.get_dashboard_data()['buckets']
            if b['key'] == 'flagged'
        )
        self.assertEqual(after, before + 1)

    def test_coming_up_lists_only_future_scheduled_notices(self):
        Notification = self.env['velkio.notification']
        soon = Notification.create({
            'name': 'Soon', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=30),
            'audience': 'me', 'state': 'scheduled',
        })
        rows = Notification.get_dashboard_data()['next_up']
        self.assertIn(soon.id, [r['id'] for r in rows])
        for row in rows:
            for key in ('id', 'name', 'level', 'flagged', 'notify_datetime'):
                self.assertIn(key, row)

    def test_the_dashboard_works_for_a_plain_user(self):
        staff = self.env['res.users'].create({
            'name': 'Plain', 'login': 'velkio_dash_user', 'email': 'pd@example.com',
        })
        data = self.env['velkio.notification'].with_user(staff).get_dashboard_data()
        self.assertEqual(len(data['buckets']), 7)


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioPerUserVisibility(odoo.tests.TransactionCase):
    """Everything is per person: who sees it, who may change it, who starred it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = cls.env['res.users'].create({
            'name': 'Author', 'login': 'velkio_author', 'email': 'a@example.com',
            'groups_id': [(4, cls.env.ref('velkio_reminders_notification.group_velkio_manager').id)],
        })
        cls.target = cls.env['res.users'].create({
            'name': 'Target', 'login': 'velkio_target', 'email': 't@example.com',
        })
        cls.stranger = cls.env['res.users'].create({
            'name': 'Stranger', 'login': 'velkio_stranger', 'email': 's@example.com',
        })
        cls.notice = cls.env['velkio.notification'].with_user(cls.author).create({
            'name': 'For the target',
            'body': '<p>Please read.</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'users',
            'user_ids': [(6, 0, [cls.target.id])],
        })

    # ── visibility ────────────────────────────────────────────

    def test_the_author_sees_it(self):
        visible = self.env['velkio.notification'].with_user(self.author).search([])
        self.assertIn(self.notice.id, visible.ids)

    def test_the_person_it_is_assigned_to_sees_it_before_it_is_sent(self):
        """Assigning is enough — no need to wait for the popup to fire."""
        visible = self.env['velkio.notification'].with_user(self.target).search([])
        self.assertIn(
            self.notice.id, visible.ids,
            'Someone a notice is addressed to must see it straight away.',
        )

    def test_an_unrelated_person_does_not_see_it(self):
        visible = self.env['velkio.notification'].with_user(self.stranger).search([])
        self.assertNotIn(self.notice.id, visible.ids)

    def test_a_recipient_of_a_company_wide_notice_sees_it(self):
        everyone = self.env['velkio.notification'].with_user(self.author).create({
            'name': 'To everybody', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'all', 'state': 'scheduled',
        })
        everyone._dispatch()
        visible = self.env['velkio.notification'].with_user(self.stranger).search([])
        self.assertIn(everyone.id, visible.ids)

    # ── who may edit ──────────────────────────────────────────

    def test_the_author_can_edit(self):
        self.notice.with_user(self.author).write({'name': 'Renamed'})
        self.assertEqual(self.notice.name, 'Renamed')

    def test_the_recipient_cannot_edit(self):
        with self.assertRaises(AccessError):
            self.notice.with_user(self.target).write({'name': 'Hijacked'})

    def test_the_recipient_cannot_delete(self):
        with self.assertRaises(AccessError):
            self.notice.with_user(self.target).unlink()

    def test_can_edit_flag_matches_reality(self):
        self.assertTrue(self.notice.with_user(self.author).can_edit)
        self.assertFalse(self.notice.with_user(self.target).can_edit)

    # ── flagging is personal ──────────────────────────────────

    def test_starring_shows_only_for_the_person_who_starred(self):
        as_target = self.notice.with_user(self.target)
        as_target.action_toggle_flag()

        self.assertTrue(as_target.can_edit is False, 'A reader may still star it.')
        self.assertTrue(self.notice.with_user(self.target).flagged)
        self.assertFalse(
            self.notice.with_user(self.author).flagged,
            'One person starring a notice must not flag it for anyone else.',
        )

    def test_the_flagged_search_is_per_user(self):
        Notification = self.env['velkio.notification']
        self.notice.with_user(self.target).action_toggle_flag()

        target_flagged = Notification.with_user(self.target).search([('flagged', '=', True)])
        author_flagged = Notification.with_user(self.author).search([('flagged', '=', True)])
        self.assertIn(self.notice.id, target_flagged.ids)
        self.assertNotIn(self.notice.id, author_flagged.ids)

    def test_unstarring_only_removes_your_own_star(self):
        self.notice.with_user(self.target).action_toggle_flag()
        self.notice.with_user(self.author).action_toggle_flag()
        self.assertEqual(len(self.notice.flag_user_ids), 2)

        self.notice.with_user(self.target).action_toggle_flag()
        self.assertEqual(self.notice.flag_user_ids, self.author)

    def test_the_flagged_dashboard_bucket_is_per_user(self):
        Notification = self.env['velkio.notification']
        self.notice.with_user(self.target).action_toggle_flag()

        def flagged_count(user):
            data = Notification.with_user(user).get_dashboard_data()
            return next(b['count'] for b in data['buckets'] if b['key'] == 'flagged')

        self.assertEqual(flagged_count(self.target), 1)
        self.assertEqual(
            flagged_count(self.author), 0,
            'The Flagged tile must count only what the person looking at it starred.',
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioDesktopNotifications(odoo.tests.TransactionCase):
    """The same reminder must also be able to reach the operating system."""

    def setUp(self):
        super().setUp()
        self.reader = self.env['res.users'].create({
            'name': 'Desktop', 'login': 'velkio_desktop', 'email': 'd@example.com',
        })

    def _notice(self, **kw):
        values = {
            'name': 'System notice',
            'body': '<p>Please <strong>save your work</strong> before 6&nbsp;PM.</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=5),
            'audience': 'users', 'user_ids': [(6, 0, [self.reader.id])],
        }
        values.update(kw)
        return self.env['velkio.notification'].create(values)

    def test_the_payload_carries_a_plain_text_body(self):
        """The operating system shows text, never markup."""
        payload = self._notice()._payload(self.reader)
        self.assertTrue(payload['desktop'], 'On by default.')
        body = payload['desktop_body']
        self.assertNotIn('<strong>', body, 'Markup must be stripped for the OS.')
        self.assertNotIn('&nbsp;', body, 'Entities must be resolved for the OS.')
        self.assertIn('save your work', body)

    def test_a_reader_can_switch_system_notifications_off(self):
        self.reader.velkio_desktop_enabled = False
        payload = self._notice()._payload(self.reader)
        self.assertFalse(payload['desktop'])
        # The in-Odoo popup is unaffected by that choice.
        self.assertEqual(payload['title'], 'System notice')

    def test_the_preference_is_editable_by_its_owner(self):
        self.reader.with_user(self.reader).write({'velkio_desktop_enabled': False})
        self.assertFalse(self.reader.velkio_desktop_enabled)

    def test_a_long_message_is_trimmed_for_the_system_tray(self):
        notice = self._notice(body='<p>%s</p>' % ('word ' * 200))
        self.assertLessEqual(len(notice._payload(self.reader)['desktop_body']), 220)

    def test_the_payload_carries_an_icon_for_the_system_tray(self):
        """The entry in the notification list should be identifiable."""
        payload = self._notice()._payload(self.reader)
        self.assertTrue(payload['icon'].endswith('.png'))
        self.assertIn('velkio_reminders_notification', payload['icon'])



@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioHeroLayout(odoo.tests.TransactionCase):
    """The reminder card is the shipped default."""

    def test_the_default_style_is_the_centred_reminder_card(self):
        style = self.env['velkio.popup.style'].get_default_style()
        payload = style._as_payload()
        self.assertEqual(payload['position'], 'top-center')
        self.assertEqual(payload['animation'], 'drop')

    def test_each_shipped_style_is_a_different_design(self):
        """Six styles, six distinct skins — not one card in six colours."""
        Style = self.env['velkio.popup.style']
        styles = Style.search([])
        declared = {key for key, _label in Style._fields['skin'].selection}

        self.assertEqual(len(styles), len(declared))
        self.assertEqual(
            set(styles.mapped('skin')), declared,
            'Every design offered in the form should ship as a ready style.',
        )
        self.assertEqual(
            len(set(styles.mapped('skin'))), len(styles),
            'Two shipped styles use the same design.',
        )
        for style in styles:
            self.assertIn(style._as_payload()['skin'], declared)

    def test_acknowledgement_notices_never_count_down(self):
        """A popup asking for an answer must not show a pointless timer."""
        notice = self.env['velkio.notification'].create({
            'name': 'Ack', 'body': '<p>x</p>', 'require_ack': True, 'duration': 30,
            'notify_datetime': fields.Datetime.now() + timedelta(minutes=5),
            'audience': 'me',
        })
        self.assertEqual(notice._payload(self.env.user)['duration'], 0)
