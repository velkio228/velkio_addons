from unittest.mock import patch
from odoo.tests import TransactionCase, tagged, new_test_user
from odoo.exceptions import UserError, AccessError, ValidationError

MODULE = 'velkio_easy_pos_with_whatsapp_integration'

@tagged('post_install', '-at_install')
class TestVelkioPOS(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cashier = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True)), login='velkio_cashier_test', groups='base.group_user,'+MODULE+'.group_pos_screen_user')
        cls.other = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True)), login='velkio_other_test', groups='base.group_user,'+MODULE+'.group_pos_screen_user')
        cls.manager = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True)), login='velkio_manager_test', groups='base.group_user,'+MODULE+'.group_pos_screen_manager')
        cls.config = cls.env.ref(MODULE+'.config_main_counter')
        cls.payment = cls.env.ref(MODULE+'.payment_method_cash')
        cls.product = cls.env['product.product'].create({'name':'Velkio Test Item','type':'product','list_price':100,'taxes_id':[(5,0,0)]})
        cls.partner = cls.env['res.partner'].create({'name':'Test Customer','mobile':'+919876543210'})

    def order(self, user=None, qty=2):
        user = user or self.cashier
        return self.env['pos.screen.order'].with_user(user).create({
            'config_id':self.config.id,'payment_method_id':self.payment.id,
            'partner_id':self.partner.id,'line_ids':[(0,0,{'product_id':self.product.id,'product_uom_id':self.product.uom_id.id,'qty':qty,'price_unit':100})]})

    def test_cashier_payment_and_repeat(self):
        order=self.order()
        self.assertEqual(order.amount_total,200)
        order.action_mark_paid()
        order.action_mark_paid()
        self.assertEqual(order.state,'paid')
        with self.assertRaises(UserError): order.action_cancel()
        with self.assertRaises(UserError): order.action_draft()

    def test_cancelled_bill_cannot_pay(self):
        order=self.order(); order.action_cancel()
        with self.assertRaises(UserError): order.action_mark_paid()
        order.action_draft(); self.assertEqual(order.state,'draft')

    def test_order_and_line_ownership(self):
        order=self.order()
        with self.assertRaises(AccessError): order.with_user(self.other).read(['name'])
        with self.assertRaises(AccessError): order.line_ids.with_user(self.other).read(['qty'])
        self.assertEqual(order.with_user(self.manager).amount_total,200)

    def test_counter_assignment(self):
        self.config.user_ids=self.other
        with self.assertRaises(UserError): self.env['pos.screen.order'].with_user(self.cashier)._screen_config(self.config.id)

    def test_cashier_screen_bootstrap(self):
        result=self.env['pos.screen.order'].with_user(self.cashier).get_screen_config()
        self.assertTrue(result['configs'])

    def test_ui_save_load(self):
        model=self.env['pos.screen.order'].with_user(self.cashier)
        payload={'company_id':self.env.company.id,'config_id':self.config.id,'payment_method_id':self.payment.id,'partner_id':self.partner.id,'lines':[{'product_id':self.product.id,'qty':2,'price_unit':100,'discount':10}]}
        result=model.create_from_ui(payload)
        self.assertEqual(result['amount_total'],180)
        loaded=model.load_order(result['order_id']);self.assertEqual(len(loaded['lines']),1)
        payload.update(order_id=result['order_id'],paid=True)
        self.assertEqual(model.create_from_ui(payload)['state'],'paid')
        with self.assertRaises(UserError): model.create_from_ui(payload)

    def test_stock_duplicate_lines_and_delivery(self):
        warehouse=self.env['stock.warehouse'].search([('company_id','=',self.env.company.id)],limit=1)
        self.config.write({'picking_type_id':warehouse.out_type_id.id,'location_src_id':warehouse.lot_stock_id.id,'location_dest_id':self.env.ref('stock.stock_location_customers').id,'deliver_on_payment':True,'allow_negative_stock':False})
        self.env['stock.quant']._update_available_quantity(self.product,warehouse.lot_stock_id,3)
        order=self.order()
        order.line_ids.copy({'order_id':order.id})
        with self.assertRaises(UserError): order.action_mark_paid()
        order.line_ids[-1:].unlink()
        order.action_mark_paid()
        self.assertEqual(order.picking_id.state,'done')
        self.assertEqual(self.product.with_context(location=warehouse.lot_stock_id.id).qty_available,1)

    def test_whatsapp_failure_keeps_payment(self):
        order=self.order()
        template=self.env.ref(MODULE+'.whatsapp_template_pos_screen_bill')
        self.config.write({'whatsapp_template_id':template.id,'whatsapp_send_on_payment':True})
        order.action_mark_paid()
        self.assertEqual(order.state,'paid')
        self.assertEqual(order.whatsapp_state,'failed')

    def test_repeated_payment_does_not_send_again(self):
        order=self.order()
        self.config.write({'whatsapp_template_id':self.env.ref(MODULE+'.whatsapp_template_pos_screen_bill').id,'whatsapp_send_on_payment':True})
        with patch.object(type(order),'_send_whatsapp_bill',return_value=1) as send:
            order.action_mark_paid(); order.action_mark_paid()
            self.assertEqual(send.call_count,1)

    def test_manual_send_requires_paid(self):
        order=self.order()
        with self.assertRaises(UserError): order.action_send_whatsapp()
        order.action_mark_paid()
        self.assertEqual(order.action_send_whatsapp()['res_model'],'whatsapp.composer')

    def test_tax_and_receipt(self):
        tax=self.env['account.tax'].create({'name':'Test 10%','amount':10,'type_tax_use':'sale'})
        order=self.order(self.manager)
        order.line_ids.tax_ids=tax
        self.assertEqual(order.amount_total,220)
        report=self.env.ref(MODULE+'.action_report_pos_screen_order')
        content,_=report._render_qweb_html(report.report_name,order.ids)
        self.assertIn(b'Velkio Test Item',content)

    def test_phone_normalization(self):
        model=self.env['pos.screen.order']
        self.assertEqual(model._normalize_phone('+91 98765-43210'),'+919876543210')
        self.assertEqual(model._normalize_phone('Customer 12345678'),'')

    def test_paid_bill_is_immutable(self):
        order = self.order()
        order.action_mark_paid()
        with self.assertRaises(UserError): order.write({'partner_id':False})
        with self.assertRaises(UserError): order.line_ids.write({'price_unit':1})
        with self.assertRaises(UserError): order.line_ids.unlink()
        with self.assertRaises(UserError): self.order().write({'state':'paid'})

    def _approved_template(self):
        account = self.env['whatsapp.account'].create({
            'name':'Offline Test Account','app_uid':'test-app','app_secret':'test-secret',
            'account_uid':'test-account','phone_uid':'test-phone','token':'test-token',
            'allowed_company_ids':[(6,0,self.env.company.ids)], 'notify_user_ids':[(6,0,self.cashier.ids)]})
        template = self.env.ref(MODULE+'.whatsapp_template_pos_screen_bill')
        template.write({'wa_account_id':account.id,'status':'approved'})
        self.config.write({'whatsapp_template_id':template.id,'whatsapp_send_on_payment':True})
        return template

    def test_real_whatsapp_queue_and_delivery_callbacks(self):
        self._approved_template()
        order=self.order()
        # _send(force_send_by_cron=True) queues only; no Meta network calls.
        order.action_mark_paid()
        self.assertEqual(order.whatsapp_state,'queued')
        self.assertTrue(order.whatsapp_message_id)
        message=order.whatsapp_message_id.sudo()
        self.assertEqual(message.mail_message_id.res_id,order.id)
        self.assertEqual(message.mobile_number, self.partner.mobile)
        message.write({'state':'delivered'})
        self.assertEqual(order.whatsapp_state,'sent')
        message.write({'state':'error','failure_reason':'Offline test failure'})
        self.assertEqual(order.whatsapp_state,'failed')
        self.assertEqual(order.whatsapp_error,'Offline test failure')

    def test_invalid_number_queue_does_not_claim_queued(self):
        self._approved_template()
        order=self.order()
        order.whatsapp_number_manual='abc'
        order.action_mark_paid()
        self.assertEqual(order.state,'paid')
        self.assertEqual(order.whatsapp_state,'failed')

    def test_template_permission_error_keeps_payment(self):
        self._approved_template()
        order=self.order()
        with patch.object(type(order),'_whatsapp_blocking_reason',side_effect=AccessError('test template restricted')):
            order.action_mark_paid()
        self.assertEqual(order.state,'paid')
        self.assertEqual(order.whatsapp_state,'failed')

    def test_old_callback_cannot_replace_latest_message(self):
        self._approved_template()
        order=self.order();order.action_mark_paid()
        old=order.whatsapp_message_id.sudo()
        order._send_whatsapp_bill()
        latest=order.whatsapp_message_id
        self.assertNotEqual(old,latest)
        old.write({'state':'error','failure_reason':'late old failure'})
        self.assertEqual(order.whatsapp_message_id,latest)
        self.assertEqual(order.whatsapp_state,'queued')

    def test_wrong_company_rejected(self):
        company=self.env['res.company'].create({'name':'Other Test Company'})
        with self.assertRaises(UserError):
            self.env['pos.screen.order'].with_user(self.cashier)._screen_company(company.id)

    def test_whatsapp_override_survives_draft_reload(self):
        order=self.order()
        order.whatsapp_number_manual='+919123456789'
        self.assertEqual(order.load_order(order.id)['whatsapp_number_manual'],'+919123456789')

    def test_cashier_cannot_configure_manager_can(self):
        with self.assertRaises(AccessError): self.config.with_user(self.cashier).write({'receipt_footer':'cashier'})
        self.config.with_user(self.manager).write({'receipt_footer':'manager'})
        self.assertEqual(self.config.receipt_footer,'manager')

    def test_product_search_and_customer_number(self):
        model=self.env['pos.screen.order'].with_user(self.cashier)
        products=model.search_products('Velkio Test',config_id=self.config.id)
        self.assertTrue(products)
        customer=model.find_or_create_partner_by_number('+919876543210')
        self.assertEqual(customer['id'],self.partner.id)

    def test_discount_validation(self):
        order=self.order()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order.line_ids.discount=101

    def test_settings_admin_full_workflow(self):
        order=self.order(self.env.ref('base.user_admin'))
        order.action_confirm();order.action_mark_paid()
        self.assertEqual(order.state,'paid')

    def test_confirmed_bill_can_pay_from_screen_without_editing(self):
        order=self.order(); order.action_confirm()
        result=order.create_from_ui({'order_id':order.id,'company_id':order.company_id.id,'config_id':order.config_id.id,'payment_method_id':order.payment_method_id.id,'confirm':True,'paid':True,'lines':[{'product_id':self.product.id,'qty':20,'price_unit':1}]})
        self.assertEqual(result['state'],'paid')
        self.assertEqual(order.amount_total,200)

    def test_matching_phone_suffix_does_not_select_wrong_customer(self):
        wrong=self.env['res.partner'].create({'name':'Wrong Contact','mobile':'+449876543210'})
        result=self.env['pos.screen.order'].find_or_create_partner_by_number('+919876543210')
        self.assertEqual(result['id'],self.partner.id)
        self.assertNotEqual(result['id'],wrong.id)
