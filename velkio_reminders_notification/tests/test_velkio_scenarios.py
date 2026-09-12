# -*- coding: utf-8 -*-
"""End-to-end scenarios across several people at once.

These go beyond "does the method work" and walk through what actually happens
when an administrator, a manager and ordinary staff use the module together.
"""
import json
from datetime import timedelta

import odoo.tests
from odoo import fields
from odoo.exceptions import AccessError, ValidationError


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioTeamScenarios(odoo.tests.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_group = cls.env.ref('velkio_reminders_notification.group_velkio_manager')
        Users = cls.env['res.users']
        cls.boss = Users.create({
            'name': 'Boss', 'login': 'sc_boss', 'email': 'boss@example.com',
            'groups_id': [(4, cls.manager_group.id)],
        })
        cls.alice = Users.create({
            'name': 'Alice', 'login': 'sc_alice', 'email': 'alice@example.com',
        })
        cls.bob = Users.create({
            'name': 'Bob', 'login': 'sc_bob', 'email': 'bob@example.com',
        })
        cls.carol = Users.create({
            'name': 'Carol', 'login': 'sc_carol', 'email': 'carol@example.com',
        })
        cls.staff = cls.alice | cls.bob | cls.carol

    def _as(self, user):
        return self.env['velkio.notification'].with_user(user)

    # ── SCENARIO: the boss tells the whole company ────────────

    def test_company_wide_announcement(self):
        """A manager announces to everyone; every person gets exactly one row."""
        notice = self._as(self.boss).create({
            'name': 'Office closed on Friday',
            'body': '<p>The office is closed this Friday.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'all', 'state': 'scheduled',
        })
        notice._dispatch()

        internal = self.env['res.users'].search([
            ('active', '=', True), ('share', '=', False),
        ])
        self.assertEqual(notice.recipient_count, len(internal))
        for person in self.staff:
            rows = notice.recipient_ids.filtered(lambda r: r.user_id == person)
            self.assertEqual(len(rows), 1, '%s must be notified exactly once.' % person.name)

        # And each of them can see it, while none of them can change it.
        for person in self.staff:
            self.assertIn(notice.id, self._as(person).search([]).ids)
            with self.assertRaises(AccessError):
                notice.with_user(person).write({'name': 'edited'})

    def test_each_person_answers_independently(self):
        notice = self._as(self.boss).create({
            'name': 'Please confirm', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
            'require_ack': True, 'state': 'scheduled',
        })
        notice._dispatch()
        self.assertEqual(notice.open_count, 3)

        alice_row = notice.recipient_ids.filtered(lambda r: r.user_id == self.alice)
        alice_row.with_user(self.alice).action_mark_done()

        self.assertEqual(notice.open_count, 2, 'Only Alice has answered.')
        for person in (self.bob, self.carol):
            row = notice.recipient_ids.filtered(lambda r: r.user_id == person)
            self.assertEqual(row.state, 'sent', '%s still owes an answer.' % person.name)

    # ── SCENARIO: personal reminders stay personal ────────────

    def test_two_people_keep_separate_reminders(self):
        alice_note = self._as(self.alice).create({
            'name': "Alice's note", 'body': '<p>a</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me',
        })
        bob_note = self._as(self.bob).create({
            'name': "Bob's note", 'body': '<p>b</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me',
        })
        alice_sees = self._as(self.alice).search([]).ids
        bob_sees = self._as(self.bob).search([]).ids

        self.assertIn(alice_note.id, alice_sees)
        self.assertNotIn(bob_note.id, alice_sees)
        self.assertIn(bob_note.id, bob_sees)
        self.assertNotIn(alice_note.id, bob_sees)

    def test_a_self_reminder_only_pops_for_its_author(self):
        note = self._as(self.alice).create({
            'name': 'Mine only', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'me', 'state': 'scheduled',
        })
        note._dispatch()
        self.assertEqual(note.recipient_ids.user_id, self.alice)

    # ── SCENARIO: everyone stars their own things ─────────────

    def test_three_people_star_the_same_notice(self):
        notice = self._as(self.boss).create({
            'name': 'Shared notice', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
            'state': 'scheduled',
        })
        notice._dispatch()

        notice.with_user(self.alice).action_toggle_flag()
        notice.with_user(self.bob).action_toggle_flag()

        self.assertTrue(notice.with_user(self.alice).flagged)
        self.assertTrue(notice.with_user(self.bob).flagged)
        self.assertFalse(notice.with_user(self.carol).flagged)

        def flagged_ids(user):
            return self._as(user).search([('flagged', '=', True)]).ids

        self.assertIn(notice.id, flagged_ids(self.alice))
        self.assertIn(notice.id, flagged_ids(self.bob))
        self.assertNotIn(notice.id, flagged_ids(self.carol))

        # Carol unstarring something she never starred must not touch the others.
        notice.with_user(self.carol).action_toggle_flag()
        notice.with_user(self.carol).action_toggle_flag()
        self.assertTrue(notice.with_user(self.alice).flagged)

    # ── SCENARIO: the dashboard is personal ───────────────────

    def test_the_dashboard_differs_per_person(self):
        notice = self._as(self.boss).create({
            'name': 'For Alice only', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, [self.alice.id])],
            'level': 'urgent', 'state': 'scheduled',
        })
        notice._dispatch()

        def buckets(user):
            data = self._as(user).get_dashboard_data()
            return {b['key']: b['count'] for b in data['buckets']}

        alice, bob = buckets(self.alice), buckets(self.bob)
        self.assertGreaterEqual(alice['assigned'], 1)
        self.assertEqual(bob['assigned'], 0, 'Bob was not addressed.')
        self.assertGreaterEqual(alice['urgent'], 1)
        self.assertEqual(bob['urgent'], 0, 'Bob cannot even see it.')

        # Counting and listing must agree, for each person separately.
        for user in (self.alice, self.bob, self.boss):
            for bucket in self._as(user).get_dashboard_data()['buckets']:
                self.assertEqual(
                    bucket['count'],
                    self._as(user).search_count(bucket['domain']),
                    'Bucket %s disagrees with its own list for %s.'
                    % (bucket['key'], user.name),
                )

    # ── SCENARIO: preferences are respected per person ────────

    def test_one_person_mutes_popups_the_others_still_get_them(self):
        self.bob.velkio_popup_enabled = False
        notice = self._as(self.boss).create({
            'name': 'Normal notice', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
            'state': 'scheduled',
        })
        notice._dispatch()

        states = {r.user_id.name: r.state for r in notice.recipient_ids}
        self.assertEqual(states['Bob'], 'muted')
        self.assertEqual(states['Alice'], 'sent')
        self.assertEqual(states['Carol'], 'sent')

    def test_urgent_reaches_even_the_person_who_muted_popups(self):
        self.bob.velkio_popup_enabled = False
        notice = self._as(self.boss).create({
            'name': 'Evacuate', 'body': '<p>x</p>', 'level': 'urgent',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
            'state': 'scheduled',
        })
        notice._dispatch()
        bob_row = notice.recipient_ids.filtered(lambda r: r.user_id == self.bob)
        self.assertEqual(bob_row.state, 'sent', 'Urgent overrides the mute.')

    def test_sound_and_desktop_follow_each_person(self):
        self.alice.velkio_sound_enabled = False
        self.bob.velkio_desktop_enabled = False
        notice = self._as(self.boss).create({
            'name': 'Mixed prefs', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
        })
        self.assertFalse(notice._payload(self.alice)['sound'])
        self.assertTrue(notice._payload(self.bob)['sound'])
        self.assertFalse(notice._payload(self.bob)['desktop'])
        self.assertTrue(notice._payload(self.alice)['desktop'])

    # ── SCENARIO: an ordinary person cannot overreach ─────────

    def test_staff_cannot_broadcast(self):
        for audience, extra in (('all', {}), ('users', {'user_ids': [(6, 0, [self.bob.id])]})):
            with self.assertRaises(ValidationError):
                values = {
                    'name': 'Not allowed', 'body': '<p>x</p>',
                    'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
                    'audience': audience,
                }
                values.update(extra)
                self._as(self.alice).create(values)

    def test_staff_cannot_edit_the_style_library(self):
        style = self.env['velkio.popup.style'].search([], limit=1)
        with self.assertRaises(AccessError):
            style.with_user(self.alice).write({'name': 'hijacked'})

    def test_staff_cannot_edit_the_template_library(self):
        template = self.env['velkio.template'].search([], limit=1)
        with self.assertRaises(AccessError):
            template.with_user(self.alice).write({'title': 'hijacked'})

    def test_staff_can_still_use_a_template(self):
        """Reading and using the library is allowed; the counter uses sudo."""
        template = self.env.ref('velkio_reminders_notification.tpl_standup')
        action = template.with_user(self.alice).action_use()
        self.assertEqual(action['context']['default_template_id'], template.id)

    def test_a_manager_can_edit_anything(self):
        note = self._as(self.alice).create({
            'name': "Alice's", 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(hours=1),
            'audience': 'me',
        })
        note.with_user(self.boss).write({'name': 'Corrected by the manager'})
        self.assertEqual(note.name, 'Corrected by the manager')

    # ── SCENARIO: snooze, per person ──────────────────────────

    def test_one_person_snoozes_without_affecting_anyone_else(self):
        notice = self._as(self.boss).create({
            'name': 'Snooze test', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users', 'user_ids': [(6, 0, self.staff.ids)],
            'state': 'scheduled',
        })
        notice._dispatch()
        alice_row = notice.recipient_ids.filtered(lambda r: r.user_id == self.alice)
        alice_row.write({
            'state': 'snoozed',
            'snooze_until': fields.Datetime.now() - timedelta(minutes=1),
        })

        others = notice.recipient_ids - alice_row
        self.assertEqual(set(others.mapped('state')), {'sent'})

        self.env['velkio.notification.recipient']._cron_wake_snoozed()
        self.assertEqual(alice_row.state, 'sent', 'It came back for Alice only.')

    # ── SCENARIO: scale ───────────────────────────────────────

    def test_a_company_wide_send_stays_cheap(self):
        self.env['res.users'].create([{
            'name': 'Bulk %s' % i, 'login': 'sc_bulk_%s' % i,
            'email': 'scb%s@example.com' % i,
        } for i in range(40)])
        notice = self._as(self.boss).create({
            'name': 'Everyone', 'body': '<p>x</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'all', 'state': 'scheduled',
        })
        self.env.flush_all()
        before = self.env.cr.sql_log_count
        notice._dispatch()
        self.env.flush_all()
        used = self.env.cr.sql_log_count - before
        self.assertGreater(notice.recipient_count, 40)
        self.assertLess(
            used, 40,
            'Sending to the whole company cost %s queries for %s people; it '
            'should not scale per person.' % (used, notice.recipient_count),
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioMultiUserHttp(odoo.tests.HttpCase):
    """Two people hitting the routes at the same time."""

    def setUp(self):
        super().setUp()
        Users = self.env['res.users']
        self.boss = Users.create({
            'name': 'Boss', 'login': 'http_boss', 'password': 'http_boss_pwd',
            'email': 'hb@example.com',
            'groups_id': [(4, self.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })
        self.alice = Users.create({
            'name': 'Alice', 'login': 'http_alice', 'password': 'http_alice_pwd',
            'email': 'ha@example.com',
        })
        self.bob = Users.create({
            'name': 'Bob', 'login': 'http_bob', 'password': 'http_bob_pwd',
            'email': 'hbo@example.com',
        })
        self.notice = self.env['velkio.notification'].with_user(self.boss).create({
            'name': 'To both of you', 'body': '<p>Please read.</p>',
            'notify_datetime': fields.Datetime.now(),
            'audience': 'users',
            'user_ids': [(6, 0, [self.alice.id, self.bob.id])],
            'require_ack': True, 'state': 'scheduled',
        })
        self.notice._dispatch()

    def _call(self, route, params=None):
        return self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params or {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

    def _row(self, user):
        return self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', self.notice.id), ('user_id', '=', user.id),
        ], limit=1)

    def test_each_person_sees_only_their_own_pending_list(self):
        self.authenticate('http_alice', 'http_alice_pwd')
        alice = self._call('/velkio/notification/pending')
        self.assertEqual(alice['count'], 1)
        self.assertEqual(alice['popups'][0]['id'], self.notice.id)

        self.authenticate('http_bob', 'http_bob_pwd')
        bob = self._call('/velkio/notification/pending')
        self.assertEqual(bob['count'], 1)

    def test_one_person_answering_does_not_answer_for_the_other(self):
        self.authenticate('http_alice', 'http_alice_pwd')
        self._call('/velkio/notification/done',
                   {'notification_id': self.notice.id, 'acknowledged': True})

        self.assertEqual(self._row(self.alice).state, 'done')
        self.assertTrue(self._row(self.alice).acknowledged)
        self.assertEqual(
            self._row(self.bob).state, 'sent',
            "Alice answering must not clear Bob's copy.",
        )

        self.authenticate('http_bob', 'http_bob_pwd')
        self.assertEqual(self._call('/velkio/notification/pending')['count'], 1)

    def test_a_stranger_cannot_answer_on_someone_elses_behalf(self):
        outsider = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'http_out', 'password': 'http_out_pwd',
            'email': 'ho@example.com',
        })
        self.authenticate('http_out', 'http_out_pwd')
        result = self._call('/velkio/notification/done',
                            {'notification_id': self.notice.id})
        self.assertFalse(result.get('success'))
        self.assertEqual(self._row(self.alice).state, 'sent')
        self.assertFalse(self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', self.notice.id), ('user_id', '=', outsider.id),
        ]))

    def test_a_stranger_cannot_fire_someone_elses_reminder(self):
        outsider = self.env['res.users'].create({
            'name': 'Outsider2', 'login': 'http_out2', 'password': 'http_out2_pwd',
            'email': 'ho2@example.com',
        })
        self.authenticate('http_out2', 'http_out2_pwd')
        result = self._call('/velkio/notification/fire',
                            {'notification_id': self.notice.id})
        self.assertFalse(result['ok'])

    def test_snoozing_is_per_person(self):
        self.authenticate('http_alice', 'http_alice_pwd')
        self._call('/velkio/notification/snooze',
                   {'notification_id': self.notice.id, 'minutes': 30})
        self.assertEqual(self._row(self.alice).state, 'snoozed')
        self.assertEqual(self._row(self.bob).state, 'sent')

    def test_a_bad_id_is_refused_rather_than_crashing(self):
        self.authenticate('http_alice', 'http_alice_pwd')
        for value in ('not-a-number', 0, -1, 999999999):
            result = self._call('/velkio/notification/done',
                                {'notification_id': value})
            self.assertFalse(result.get('success'), 'Refused %r' % value)


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioBacklog(odoo.tests.HttpCase):
    """Signing in after a few days away must not bury the screen."""

    def setUp(self):
        super().setUp()
        self.boss = self.env['res.users'].create({
            'name': 'Boss', 'login': 'bl_boss', 'email': 'blb@example.com',
            'groups_id': [(4, self.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })
        self.away = self.env['res.users'].create({
            'name': 'Away', 'login': 'bl_away', 'password': 'bl_away_pwd',
            'email': 'bla@example.com',
        })

    def _send(self, title, days_ago):
        """Send it, then backdate the delivery.

        In production the cron dispatches a notice when it falls due, so its
        sent_at is the moment it actually appeared. Dispatching here happens
        now, so the row is moved back to model a real absence.
        """
        when = fields.Datetime.now() - timedelta(days=days_ago)
        notice = self.env['velkio.notification'].with_user(self.boss).create({
            'name': title, 'body': '<p>%s</p>' % title,
            'notify_datetime': when,
            'audience': 'users', 'user_ids': [(6, 0, [self.away.id])],
            'state': 'scheduled',
        })
        notice._dispatch()
        notice.recipient_ids.write({'sent_at': when})
        return notice

    def test_the_backlog_is_capped_and_still_counted(self):
        """Eight missed reminders come back as a short list, not all eight."""
        for i in range(8):
            self._send('Missed %s' % i, days_ago=2)

        self.authenticate('bl_away', 'bl_away_pwd')
        result = self.url_open(
            '/velkio/notification/pending',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

        self.assertEqual(result['count'], 8, 'The bell still shows everything.')
        self.assertLessEqual(
            len(result['popups']), 5,
            'The replay is capped so a long absence cannot flood the screen.',
        )

    def test_anything_older_than_a_week_is_left_in_the_list(self):
        old = self._send('Ancient', days_ago=30)
        recent = self._send('Recent', days_ago=1)

        self.authenticate('bl_away', 'bl_away_pwd')
        result = self.url_open(
            '/velkio/notification/pending',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

        shown = [p['id'] for p in result['popups']]
        self.assertIn(recent.id, shown)
        self.assertNotIn(old.id, shown, 'A month-old notice should not pop up.')


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioNoDoublePopup(odoo.tests.TransactionCase):
    """The same notice must not arrive twice.

    The browser arms its own timer so a popup lands on the exact second, up to
    a minute before the cron catches up. The cron used to reset the recipient
    row and push the very same popup again, so a reminder that had already been
    answered reappeared moments later.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = cls.env['res.users'].create({
            'name': 'Reader', 'login': 'dp_reader', 'email': 'dp@example.com',
        })

    def _notice(self, **vals):
        values = {
            'name': 'Month-end close today',
            'body': '<p>Post the last entries.</p>',
            'notify_datetime': fields.Datetime.now() - timedelta(seconds=30),
            'audience': 'users',
            'user_ids': [(6, 0, [self.reader.id])],
            'state': 'scheduled',
        }
        values.update(vals)
        return self.env['velkio.notification'].create(values)

    def _pushes(self, notice, force=False):
        """How many bus messages this dispatch sends to our reader."""
        Bus = self.env['bus.bus']
        before = Bus.search_count([])
        notice._dispatch(force=force)
        self.env.cr.precommit.run()
        return Bus.search_count([]) - before

    def _row(self, notice):
        return self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', notice.id),
            ('user_id', '=', self.reader.id),
        ])

    def test_the_cron_does_not_repush_an_answered_notice(self):
        notice = self._notice()
        self.assertEqual(self._pushes(notice), 1, 'The first send goes out.')

        self._row(notice).write({'state': 'done'})
        notice.state = 'scheduled'          # as if the cron had not run yet

        self.assertEqual(
            self._pushes(notice), 0,
            'A notice already answered must not be pushed a second time.',
        )
        self.assertEqual(
            self._row(notice).state, 'done',
            'Answering it must not be undone by a later dispatch.',
        )

    def test_the_cron_does_not_repush_one_already_on_screen(self):
        notice = self._notice()
        self._pushes(notice)
        # What /fire + /seen leave behind when the browser's timer wins the race.
        self._row(notice).write({'state': 'seen'})
        notice.state = 'scheduled'

        self.assertEqual(
            self._pushes(notice), 0,
            'It is already on their screen; pushing again duplicates it.',
        )

    def test_a_snoozed_notice_is_left_alone(self):
        notice = self._notice()
        self._pushes(notice)
        self._row(notice).write({
            'state': 'snoozed',
            'snooze_until': fields.Datetime.now() + timedelta(hours=1),
        })
        notice.state = 'scheduled'

        self.assertEqual(self._pushes(notice), 0)
        self.assertEqual(
            self._row(notice).state, 'snoozed',
            'Putting it off must survive a dispatch.',
        )

    def test_send_now_reaches_someone_who_already_answered(self):
        """The explicit button is a deliberate re-send, so it still goes out."""
        notice = self._notice()
        self._pushes(notice)
        self._row(notice).write({'state': 'done'})

        self.assertEqual(self._pushes(notice, force=True), 1)
        self.assertEqual(self._row(notice).state, 'sent')

    def test_a_reader_not_yet_served_still_gets_it(self):
        """Skipping the served must not skip everybody."""
        latecomer = self.env['res.users'].create({
            'name': 'Latecomer', 'login': 'dp_late', 'email': 'late@example.com',
        })
        notice = self._notice()
        self._pushes(notice)
        self._row(notice).write({'state': 'done'})

        notice.user_ids = [(4, latecomer.id)]
        notice.state = 'scheduled'
        self.assertEqual(
            self._pushes(notice), 1,
            'The new reader is served even though the first one is finished.',
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioReadState(odoo.tests.TransactionCase):
    """The eye in the list: read is per person, and unread is what the bell counts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.manager_group = cls.env.ref('velkio_reminders_notification.group_velkio_manager')
        cls.sender = Users.create({
            'name': 'Sender', 'login': 'rd_sender', 'email': 'rds@example.com',
            'groups_id': [(4, cls.manager_group.id)],
        })
        cls.anna = Users.create({
            'name': 'Anna', 'login': 'rd_anna', 'email': 'anna@example.com'})
        cls.ben = Users.create({
            'name': 'Ben', 'login': 'rd_ben', 'email': 'ben@example.com'})

    def _sent_to(self, users, name='Submit your expenses'):
        notice = self.env['velkio.notification'].with_user(self.sender).create({
            'name': name, 'body': '<p>Before Friday, please.</p>',
            'notify_datetime': fields.Datetime.now() - timedelta(minutes=1),
            'audience': 'users', 'user_ids': [(6, 0, [u.id for u in users])],
            'state': 'scheduled',
        })
        notice._dispatch()
        return notice

    def _unread_for(self, user):
        return self.env['velkio.notification.recipient'].with_user(
            user)._unread_count()

    def test_a_delivered_notice_starts_unread(self):
        notice = self._sent_to([self.anna])
        self.assertFalse(notice.with_user(self.anna).is_read)
        self.assertEqual(self._unread_for(self.anna), 1)

    def test_opening_it_marks_it_read(self):
        notice = self._sent_to([self.anna])
        # The form asks for the body; that is what tells us it was opened.
        notice.with_user(self.anna).web_read({'name': {}, 'body': {}})

        self.assertTrue(notice.with_user(self.anna).is_read)
        self.assertEqual(
            self._unread_for(self.anna), 0,
            'Once read it leaves the bell.',
        )

    def test_the_list_does_not_mark_anything_read(self):
        """Only a real open counts, not the list refreshing behind it."""
        notice = self._sent_to([self.anna])
        notice.with_user(self.anna).web_read({'name': {}, 'level': {}})

        self.assertFalse(notice.with_user(self.anna).is_read)
        self.assertEqual(self._unread_for(self.anna), 1)

    def test_read_is_per_person(self):
        notice = self._sent_to([self.anna, self.ben])
        notice.with_user(self.anna).web_read({'body': {}})

        self.assertTrue(notice.with_user(self.anna).is_read)
        self.assertFalse(
            notice.with_user(self.ben).is_read,
            "Anna reading it must not clear Ben's.",
        )
        self.assertEqual(self._unread_for(self.anna), 0)
        self.assertEqual(self._unread_for(self.ben), 1)

    def test_the_eye_toggles_both_ways(self):
        notice = self._sent_to([self.anna])
        mine = notice.with_user(self.anna)

        mine.action_toggle_read()
        self.assertTrue(mine.is_read)
        self.assertEqual(self._unread_for(self.anna), 0)

        mine.action_toggle_read()
        self.assertFalse(mine.is_read, 'It can be put back to unread.')
        self.assertEqual(self._unread_for(self.anna), 1)

    def test_answering_the_popup_reads_it(self):
        notice = self._sent_to([self.anna])
        row = self.env['velkio.notification.recipient'].search([
            ('notification_id', '=', notice.id), ('user_id', '=', self.anna.id)])
        row.write({'state': 'done', 'done_at': fields.Datetime.now()})
        row._mark_read()

        self.assertTrue(notice.with_user(self.anna).is_read)
        self.assertEqual(self._unread_for(self.anna), 0)

    def test_unread_filter_shows_only_my_own(self):
        hers = self._sent_to([self.anna], name='Hers')
        his = self._sent_to([self.ben], name='His')
        both = self._sent_to([self.anna, self.ben], name='Both')
        both.with_user(self.anna).web_read({'body': {}})

        unread = self.env['velkio.notification'].with_user(self.anna).search(
            [('is_read', '=', False), ('id', 'in', (hers + his + both).ids)])
        self.assertIn(hers, unread)
        self.assertNotIn(both, unread, 'Anna has read that one.')
        self.assertNotIn(his, unread, 'It was never sent to Anna.')

    def test_a_notice_never_sent_to_me_is_not_in_my_count(self):
        self._sent_to([self.ben])
        self.assertEqual(
            self._unread_for(self.anna), 0,
            "Someone else's notice must not sit in Anna's bell.",
        )

    def test_a_reader_may_mark_their_own_state_without_write_access(self):
        """Read and flag are the reader's own, not the author's.

        A recipient cannot edit someone else's notice, and must not need to:
        both fields live on their own side record.
        """
        notice = self._sent_to([self.anna])
        mine = notice.with_user(self.anna)

        self.assertFalse(mine.can_edit, 'Anna is not the author.')
        with self.assertRaises(AccessError):
            mine.write({'name': 'Renamed by a reader'})

        mine.action_toggle_read()
        self.assertTrue(mine.is_read)

        mine.flagged = True
        self.assertTrue(mine.flagged)
        self.assertFalse(
            notice.with_user(self.ben).flagged,
            'A star is the reader\'s own.',
        )


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioStackLimit(odoo.tests.TransactionCase):
    """A burst of notices must queue, not bury the screen."""

    def test_one_card_at_a_time_by_default(self):
        style = self.env['velkio.popup.style'].create({'name': 'Fresh'})
        self.assertEqual(
            style.stack_limit, 1,
            'The default card is large; more than one fills the screen.',
        )

    def test_the_shipped_default_style_shows_one(self):
        style = self.env.ref(
            'velkio_reminders_notification.style_reminder_card')
        self.assertEqual(style.stack_limit, 1)

    def test_the_payload_carries_the_limit_to_the_browser(self):
        payload = self.env['velkio.popup.style'].default_payload()
        self.assertEqual(payload['stack_limit'], 1)

    def test_a_deliberate_choice_is_still_allowed(self):
        style = self.env['velkio.popup.style'].create(
            {'name': 'Busy wall', 'stack_limit': 3})
        self.assertEqual(style.stack_limit, 3)


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioCloseAll(odoo.tests.HttpCase):
    """Clearing the screen is not the same as reading."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.sender = Users.create({
            'name': 'Sender', 'login': 'ca_send', 'email': 'cas@example.com',
            'groups_id': [(4, cls.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })
        cls.anna = Users.create({
            'name': 'Anna', 'login': 'ca_anna', 'password': 'ca_anna',
            'email': 'ca_anna@example.com',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })
        cls.ben = Users.create({
            'name': 'Ben', 'login': 'ca_ben', 'email': 'ca_ben@example.com',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })

    def _send(self, title, users, **vals):
        values = {
            'name': title, 'body': '<p>%s</p>' % title,
            'notify_datetime': fields.Datetime.now() - timedelta(minutes=1),
            'audience': 'users', 'user_ids': [(6, 0, [u.id for u in users])],
            'state': 'scheduled',
        }
        values.update(vals)
        notice = self.env['velkio.notification'].with_user(self.sender).create(values)
        notice._dispatch()
        return notice

    def _rows_for(self, user):
        return self.env['velkio.notification.recipient'].search(
            [('user_id', '=', user.id)])

    def _post(self, route):
        return self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}),
            headers={'Content-Type': 'application/json'},
        ).json()['result']

    def _dismiss_all_as_anna(self):
        self.authenticate('ca_anna', 'ca_anna')
        return self._post('/velkio/notification/dismiss_all')

    def test_the_screen_clears_but_nothing_is_read(self):
        for i in range(4):
            self._send('Notice %s' % i, [self.anna])

        result = self._dismiss_all_as_anna()

        self.assertEqual(len(result['dismissed']), 4)
        self.assertEqual(
            result['count'], 4,
            'They are off the screen but still unread, so the bell holds.',
        )
        rows = self._rows_for(self.anna)
        self.assertEqual(set(rows.mapped('state')), {'seen'})
        self.assertFalse(
            any(rows.mapped('read_at')),
            'Clearing the view must not mark anything read.',
        )

    def test_they_do_not_pop_back_up(self):
        self._send('Notice', [self.anna])
        self._dismiss_all_as_anna()

        again = self._post('/velkio/notification/pending')
        self.assertEqual(
            again['popups'], [],
            'A cleared notice must not reappear on the next catch-up.',
        )
        self.assertEqual(again['count'], 1, 'It is still waiting to be read.')

    def test_reading_one_afterwards_lowers_the_count(self):
        notice = self._send('Notice', [self.anna])
        self._dismiss_all_as_anna()

        notice.with_user(self.anna).web_read({'body': {}})
        self.assertEqual(
            self.env['velkio.notification.recipient'].with_user(
                self.anna)._unread_count(), 0,
        )

    def test_one_needing_acknowledgement_stays(self):
        must_ack = self._send('Sign this off', [self.anna], require_ack=True)
        self._send('Ordinary', [self.anna])

        result = self._dismiss_all_as_anna()

        self.assertEqual(len(result['dismissed']), 1)
        self.assertNotIn(
            must_ack.id, result['dismissed'],
            'A notice that demands an answer cannot be waved away.',
        )
        still_there = self._post('/velkio/notification/pending')
        self.assertIn(
            must_ack.id, [p['id'] for p in still_there['popups']],
            'It comes back until it is acknowledged.',
        )

    def test_it_leaves_a_snooze_alone(self):
        kept = self._send('Later please', [self.anna])
        self._send('Right now', [self.anna])
        row = self._rows_for(self.anna).filtered(
            lambda r: r.notification_id == kept)
        row.write({'state': 'snoozed',
                   'snooze_until': fields.Datetime.now() + timedelta(hours=2)})

        result = self._dismiss_all_as_anna()

        self.assertEqual(len(result['dismissed']), 1)
        self.assertEqual(row.state, 'snoozed', 'The snooze survives.')

    def test_it_touches_nobody_else(self):
        shared = self._send('For both of us', [self.anna, self.ben])
        self._dismiss_all_as_anna()

        bens = self._rows_for(self.ben).filtered(
            lambda r: r.notification_id == shared)
        self.assertEqual(
            bens.state, 'sent',
            "Anna clearing her screen must not clear Ben's.",
        )

    def test_it_copes_with_an_empty_queue(self):
        result = self._dismiss_all_as_anna()
        self.assertEqual(result['dismissed'], [])
        self.assertTrue(result['success'])


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioCalendar(odoo.tests.TransactionCase):
    """Each person's own reminders, laid out by date."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        cls.anna = Users.create({
            'name': 'Anna', 'login': 'cal_anna', 'email': 'cal_a@example.com'})
        cls.ben = Users.create({
            'name': 'Ben', 'login': 'cal_ben', 'email': 'cal_b@example.com'})

    def _mine_domain(self, user):
        """The domain behind the calendar's default filter, as the view holds it."""
        from lxml import etree
        from odoo.tools.safe_eval import safe_eval
        view = self.env.ref(
            'velkio_reminders_notification.velkio_notification_search_view')
        arch = etree.fromstring(view.arch)
        node = arch.find(".//filter[@name='mine_any']")
        self.assertIsNotNone(node, 'The calendar relies on this filter.')
        return safe_eval(node.get('domain'), {'uid': user.id})

    def _scheduled(self, user, name='Payroll cut-off', days=3):
        return self.env['velkio.notification'].with_user(user).create({
            'name': name, 'body': '<p>%s</p>' % name,
            'notify_datetime': fields.Datetime.now() + timedelta(days=days),
            'audience': 'me', 'state': 'scheduled',
        })

    def test_the_calendar_view_loads(self):
        view = self.env['velkio.notification'].get_view(
            self.env.ref(
                'velkio_reminders_notification'
                '.velkio_notification_calendar_view').id,
            view_type='calendar',
        )
        self.assertIn('notify_datetime', view['arch'])

    def test_it_shows_reminders_that_have_not_been_sent_yet(self):
        """A scheduled reminder has no delivery row.

        "Sent to Me" matches on those rows, so using it here left the calendar
        empty — the one thing it exists to show was the thing it hid.
        """
        notice = self._scheduled(self.anna)
        self.assertFalse(
            notice.recipient_ids,
            'Nothing is delivered until it falls due.',
        )
        found = self.env['velkio.notification'].with_user(self.anna).search(
            self._mine_domain(self.anna))
        self.assertIn(notice, found)

    def test_each_person_sees_their_own(self):
        hers = self._scheduled(self.anna, 'Hers')
        his = self._scheduled(self.ben, 'His')

        annas = self.env['velkio.notification'].with_user(self.anna).search(
            self._mine_domain(self.anna))
        self.assertIn(hers, annas)
        self.assertNotIn(his, annas, "Ben's reminders are not Anna's business.")

    def test_one_assigned_to_me_is_on_my_calendar(self):
        manager = self.env['res.users'].create({
            'name': 'Manager', 'login': 'cal_mgr', 'email': 'cal_m@example.com',
            'groups_id': [(4, self.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })
        assigned = self.env['velkio.notification'].with_user(manager).create({
            'name': 'Audit paperwork', 'body': '<p>Bring the file.</p>',
            'notify_datetime': fields.Datetime.now() + timedelta(days=2),
            'audience': 'users', 'user_ids': [(6, 0, [self.anna.id])],
            'state': 'scheduled',
        })
        annas = self.env['velkio.notification'].with_user(self.anna).search(
            self._mine_domain(self.anna))
        self.assertIn(
            assigned, annas,
            'Something addressed to me belongs on my calendar before it fires.',
        )

    def test_the_action_opens_on_that_filter(self):
        action = self.env.ref(
            'velkio_reminders_notification.action_velkio_calendar')
        self.assertIn('search_default_mine_any', action.context)
        self.assertTrue(action.view_mode.startswith('calendar'))


@odoo.tests.tagged('post_install', '-at_install')
class TestVelkioMultiDevice(odoo.tests.HttpCase):
    """One account signed in on two screens at once.

    Two separate sessions for the same person, which is what a laptop and a
    phone actually are. Everything here goes through the real HTTP endpoints,
    so it covers what each screen is told rather than what the model holds.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = cls.env['res.users'].create({
            'name': 'Two Screens', 'login': 'md_reader',
            'email': 'md@example.com',
            'groups_id': [(4, cls.env.ref('base.group_user').id)],
        })
        cls.sender = cls.env['res.users'].create({
            'name': 'Sender', 'login': 'md_sender', 'email': 'mds@example.com',
            'groups_id': [(4, cls.env.ref(
                'velkio_reminders_notification.group_velkio_manager').id)],
        })

    def _session_for(self, user):
        from odoo.http import root
        session = root.session_store.new()
        session.update({
            'db': self.env.registry.db_name, 'login': user.login,
            'uid': user.id,
            'context': dict(self.env['res.users'].with_user(user).context_get()),
            'session_token': user._compute_session_token(session.sid),
        })
        session.is_new = True
        root.session_store.save(session)
        return session.sid

    def _call(self, sid, route, params=None):
        return self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': params or {}}),
            headers={'Content-Type': 'application/json',
                     'Cookie': 'session_id=%s' % sid},
        ).json()['result']

    def _send(self, **vals):
        values = {
            'name': 'Server maintenance at 6 PM',
            'body': '<p>Save your work.</p>',
            'notify_datetime': fields.Datetime.now() - timedelta(seconds=30),
            'audience': 'users', 'user_ids': [(6, 0, [self.reader.id])],
            'state': 'scheduled',
        }
        values.update(vals)
        notice = self.env['velkio.notification'].with_user(self.sender).create(values)
        notice._dispatch()
        self.env.cr.precommit.run()
        return notice

    def setUp(self):
        super().setUp()
        self.phone = self._session_for(self.reader)
        self.laptop = self._session_for(self.reader)

    def test_both_screens_are_told_about_it(self):
        notice = self._send()
        for name, sid in (('phone', self.phone), ('laptop', self.laptop)):
            res = self._call(sid, '/velkio/notification/pending')
            self.assertIn(
                notice.id, [p['id'] for p in res['popups']],
                'The %s was not told about it.' % name,
            )
            self.assertEqual(res['count'], 1)

    def test_one_screen_showing_it_does_not_hide_it_from_the_other(self):
        """The laptop displaying it must not rob the phone of it.

        Marking a notice seen says "some screen displayed this". If that also
        stopped the catch-up, a second screen opening a moment later would
        never show the popup at all.
        """
        notice = self._send()
        self._call(self.laptop, '/velkio/notification/pending')
        self._call(self.laptop, '/velkio/notification/seen',
                   {'notification_id': notice.id})

        res = self._call(self.phone, '/velkio/notification/pending')
        self.assertIn(
            notice.id, [p['id'] for p in res['popups']],
            'The phone lost the popup because the laptop had displayed it.',
        )

    def test_answering_on_one_clears_the_other(self):
        notice = self._send()
        self._call(self.laptop, '/velkio/notification/done',
                   {'notification_id': notice.id, 'acknowledged': True})

        res = self._call(self.phone, '/velkio/notification/pending')
        self.assertEqual(res['popups'], [])
        self.assertEqual(res['count'], 0, 'And the bell clears everywhere.')

    def test_clearing_the_screen_on_one_clears_both_but_keeps_the_count(self):
        notice = self._send()
        self._call(self.laptop, '/velkio/notification/dismiss_all')

        res = self._call(self.phone, '/velkio/notification/pending')
        self.assertEqual(res['popups'], [], 'It is off both screens.')
        self.assertEqual(
            res['count'], 1,
            'But nobody read it, so it still shows in the count.',
        )

    def test_a_snooze_on_one_screen_holds_on_both(self):
        notice = self._send()
        self._call(self.laptop, '/velkio/notification/snooze',
                   {'notification_id': notice.id, 'minutes': 30})

        res = self._call(self.phone, '/velkio/notification/pending')
        self.assertEqual(
            res['popups'], [],
            'Putting it off on one screen puts it off on both.',
        )

    def test_one_that_must_be_acknowledged_survives_close_all(self):
        notice = self._send(require_ack=True)
        self._call(self.laptop, '/velkio/notification/dismiss_all')

        res = self._call(self.phone, '/velkio/notification/pending')
        self.assertIn(
            notice.id, [p['id'] for p in res['popups']],
            'It has to keep coming back until somebody answers it.',
        )

    def test_the_push_goes_to_the_account_not_to_one_session(self):
        """What makes every screen light up at once.

        The message is addressed to the person's partner, which is the channel
        every session of that account listens on. Addressing a session would
        reach one screen only.
        """
        notice = self._send()
        messages = self.env['bus.bus'].search([], order='id desc', limit=20)
        mine = [m for m in messages if 'velkio_notification' in (m.message or '')]
        self.assertTrue(mine, 'Nothing was pushed at all.')
        channels = {m.channel for m in mine}
        self.assertTrue(
            any('res.partner' in c and str(self.reader.partner_id.id) in c
                for c in channels),
            'The push was not addressed to the account: %s' % channels,
        )
