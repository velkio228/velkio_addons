# -*- coding: utf-8 -*-
import ast
import math
from collections import defaultdict
from odoo.tools.float_utils import float_compare

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang, format_date, format_datetime

from .pos_screen_config import SUPPORTED_COLUMN_TYPES

_WORKFLOW_TOKEN = object()


class PosScreenOrder(models.Model):
    _name = 'pos.screen.order'
    _description = 'Velkio Easy POS Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_order desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'))
    date_order = fields.Datetime(
        string='Order Date', required=True, default=fields.Datetime.now)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Salesperson', default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        compute='_compute_currency_id', store=True, readonly=True)
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Fiscal Position',
        check_company=True)
    config_id = fields.Many2one(
        'pos.screen.config', string='Counter', check_company=True,
        default=lambda self: self.env['pos.screen.config']._default_config().id)
    payment_method_id = fields.Many2one(
        'pos.screen.payment.method', string='Payment Method',
        check_company=True)
    payment_machine = fields.Char(
        string='Machine / Terminal', compute='_compute_payment_machine',
        store=True, readonly=False,
        help='Terminal the payment went through, kept on the bill so takings '
             'can be reconciled per machine.')
    picking_id = fields.Many2one(
        'stock.picking', string='Delivery', copy=False, readonly=True)
    picking_state = fields.Selection(
        related='picking_id.state', string='Delivery Status', readonly=True)
    note = fields.Text(string='Note')
    line_ids = fields.One2many(
        'pos.screen.order.line', 'order_id', string='Order Lines', copy=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'),
         ('paid', 'Paid'), ('cancel', 'Cancelled')],
        string='Status', default='draft', required=True, tracking=True,
        copy=False, index=True)

    amount_untaxed = fields.Monetary(
        string='Untaxed Amount', compute='_compute_amounts',
        store=True, tracking=True)
    amount_tax = fields.Monetary(
        string='Taxes', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(
        string='Total', compute='_compute_amounts', store=True, tracking=True)
    line_count = fields.Integer(
        string='Lines', compute='_compute_line_count', store=True)

    # ------------------------------------------------------------------
    # Compute / onchange
    # ------------------------------------------------------------------
    @api.depends('pricelist_id', 'company_id')
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = (
                order.pricelist_id.currency_id
                or order.company_id.currency_id
                or self.env.company.currency_id
            )

    @api.depends('line_ids.price_subtotal', 'line_ids.price_total', 'currency_id')
    def _compute_amounts(self):
        for order in self:
            rounding = order.currency_id.round if order.currency_id else (lambda v: v)
            untaxed = sum(order.line_ids.mapped('price_subtotal'))
            total = sum(order.line_ids.mapped('price_total'))
            order.amount_untaxed = rounding(untaxed)
            order.amount_total = rounding(total)
            order.amount_tax = rounding(total - untaxed)

    @api.depends('payment_method_id')
    def _compute_payment_machine(self):
        for order in self:
            order.payment_machine = order.payment_method_id.machine_name or False

    @api.depends('line_ids')
    def _compute_line_count(self):
        for order in self:
            order.line_count = len(order.line_ids)

    @api.onchange('config_id')
    def _onchange_config_id(self):
        for order in self:
            if order.config_id.pricelist_id and not order.partner_id:
                order.pricelist_id = order.config_id.pricelist_id

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for order in self:
            if not order.partner_id:
                continue
            order.pricelist_id = order.partner_id.property_product_pricelist
            order.fiscal_position_id = self.env[
                'account.fiscal.position'
            ].with_company(
                order.company_id or self.env.company
            )._get_fiscal_position(order.partner_id)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'draft') != 'draft':
                raise UserError(_('New bills must start as drafts.'))
            if vals.get('name', _('New')) == _('New'):
                company_id = vals.get('company_id') or self.env.company.id
                seq = self.env['ir.sequence'].with_company(
                    company_id).next_by_code('pos.screen.order')
                vals['name'] = seq or _('New')
        return super().create(vals_list)

    def _lock_for_payment(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        if self.ids:
            self.env.cr.execute('SELECT id FROM pos_screen_order WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset(['state', 'picking_id'])

    def _write_state(self, state):
        return self.with_context(_velkio_workflow_token=_WORKFLOW_TOKEN).write({'state': state})

    def write(self, vals):
        if 'state' in vals and self.env.context.get('_velkio_workflow_token') is not _WORKFLOW_TOKEN:
            raise UserError(_('Use the bill workflow buttons to change its status.'))
        immutable = {'company_id', 'partner_id', 'user_id', 'pricelist_id', 'fiscal_position_id',
                     'config_id', 'payment_method_id', 'payment_machine', 'line_ids', 'name'}
        if immutable.intersection(vals) and any(order.state != 'draft' for order in self):
            raise UserError(_('Only draft bills can have their customer, pricing or items changed.'))
        return super().write(vals)

    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_(
                    'Only draft or cancelled orders can be deleted. '
                    'Cancel %s first.', order.name))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        for order in self:
            if order.state != 'draft':
                raise UserError(_('Only draft bills can be confirmed.'))
            if not order.line_ids:
                raise UserError(_(
                    'Add at least one product before confirming %s.',
                    order.name))
            order._write_state('confirmed')
        return True

    def action_mark_paid(self):
        self._lock_for_payment()
        for order in self:
            if order.state == 'paid':
                continue
            if order.state not in ('draft', 'confirmed'):
                raise UserError(_('Only draft or confirmed bills can be paid.'))
            order._screen_config(order.config_id.id)
            if order.config_id.payment_method_ids and order.payment_method_id not in order.config_id.payment_method_ids:
                raise UserError(_('Select a payment method allowed by this counter.'))
            if order.state == 'draft':
                order.action_confirm()
            order._check_stock_available()
            order._write_state('paid')
            order._create_delivery()
        return True

    # ------------------------------------------------------------------
    # Stock
    # ------------------------------------------------------------------
    def _stockable_lines(self):
        """Lines that actually move stock (storable products only)."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.product_id.type == 'product' and line.qty > 0)

    def _check_stock_available(self):
        """Block payment when the counter forbids selling what is not there."""
        self.ensure_one()
        config = self.config_id
        if not config or config.allow_negative_stock or not config.location_src_id:
            return
        shortages = []
        demand = defaultdict(float)
        for line in self._stockable_lines():
            demand[line.product_id] += (line.product_uom_id or line.product_id.uom_id)._compute_quantity(
                line.qty, line.product_id.uom_id)
        for product, qty in demand.items():
            available = product.with_context(location=config.location_src_id.id).qty_available
            if float_compare(available, qty, precision_rounding=product.uom_id.rounding) < 0:
                shortages.append(_('%(product)s: %(need)s needed, %(have)s on hand',
                                   product=product.display_name, need=qty, have=available))
        if shortages:
            raise UserError(_(
                'Not enough stock at %(location)s:\n\n%(details)s',
                location=config.location_src_id.display_name,
                details='\n'.join(shortages)))

    def _prepare_picking_vals(self):
        self.ensure_one()
        config = self.config_id
        return {
            'partner_id': self.partner_id.id or False,
            'picking_type_id': config.picking_type_id.id,
            'location_id': config.location_src_id.id,
            'location_dest_id': config.location_dest_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'move_type': 'direct',
        }

    def _prepare_move_vals(self, picking, line):
        self.ensure_one()
        return {
            'name': line.product_id.display_name,
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.product_uom_id.id or line.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'company_id': self.company_id.id,
            'picking_type_id': picking.picking_type_id.id,
        }

    def _create_delivery(self):
        """Create and validate the outgoing delivery for a paid bill."""
        self.ensure_one()
        config = self.config_id
        if not config or not config.deliver_on_payment or self.picking_id:
            return self.env['stock.picking']
        lines = self._stockable_lines()
        if not lines:
            return self.env['stock.picking']

        if any(line.product_id.tracking != 'none' for line in lines):
            raise UserError(_('Automatic counter delivery supports untracked products. Use an inventory delivery with lot/serial selection for tracked products.'))
        picking = self.env['stock.picking'].create(
            self._prepare_picking_vals())
        self.env['stock.move'].create([
            self._prepare_move_vals(picking, line) for line in lines
        ])
        picking.action_confirm()
        picking.action_assign()

        # Deliver exactly what was billed, whatever the reservation managed
        # to find - a POS sale has already left the counter.
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_backorder=True)._action_done()

        self.picking_id = picking
        self.message_post(body=_(
            'Delivery %(picking)s validated from %(location)s.',
            picking=picking.name,
            location=config.location_src_id.display_name))
        return picking

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_('No delivery was created for %s.', self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        if any(order.state == 'paid' or order.picking_id.state == 'done' for order in self):
            raise UserError(_('Delivered or paid bills cannot be cancelled. Process the stock return separately.'))
        self._write_state('cancel')
        return True

    def action_draft(self):
        if any(order.state != 'cancel' for order in self):
            raise UserError(_('Only cancelled bills can be reset.'))
        self._write_state('draft')
        return True

    def action_open_pos_screen(self):
        """Reopen the POS screen loaded with this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'velkio_easy_pos_with_whatsapp_integration.screen',
            'name': _('Velkio Easy POS'),
            'params': {'order_id': self.id},
        }

    # ------------------------------------------------------------------
    # Helpers shared by the UI endpoints
    # ------------------------------------------------------------------
    def _screen_company(self, company_id=False):
        company = self.env['res.company'].browse(company_id) if company_id else self.env.company
        if company not in self.env.companies:
            raise UserError(_('This company is not available in your active companies.'))
        return company

    def _screen_pricelist(self, pricelist_id=False, partner=None):
        Pricelist = self.env['product.pricelist']
        if pricelist_id:
            return Pricelist.browse(pricelist_id)
        if partner:
            return partner.property_product_pricelist
        return Pricelist

    def _screen_price_unit(self, product, pricelist, qty, currency, partner):
        """Unit price for ``product`` honouring the pricelist, if any."""
        if pricelist:
            return pricelist._get_product_price(
                product, qty or 1.0, currency=currency, uom=product.uom_id,
                date=fields.Date.context_today(self))
        return product.lst_price

    def _screen_taxes(self, product, company, fiscal_position):
        taxes = product.taxes_id.filtered(
            lambda t: t.company_id == company)
        if fiscal_position:
            taxes = fiscal_position.map_tax(taxes)
        return taxes

    # ------------------------------------------------------------------
    # UI endpoints (called over ORM rpc by the OWL screen)
    # ------------------------------------------------------------------
    def _screen_config(self, config_id=False):
        Config = self.env['pos.screen.config']
        config = Config.browse(config_id).exists() if config_id else Config._default_config()
        if config:
            config.check_access_rights('read')
            config.check_access_rule('read')
            if config.user_ids and self.env.user not in config.user_ids:
                raise UserError(_('You are not assigned to this counter.'))
        return config

    def _screen_columns(self, config):
        """Column definitions for the suggestion list, as configured."""
        Product = self.env['product.product']
        columns = []
        for line in config.search_field_ids.sorted(lambda l: (l.sequence, l.id)):
            fname = line.field_id.name
            field = Product._fields.get(fname)
            if not field or line.field_id.ttype not in SUPPORTED_COLUMN_TYPES:
                continue  # field was removed or made unsupported since setup
            columns.append({
                'name': fname,
                'label': line.label or line.field_id.field_description,
                'width': line.width or 0,
                'align': line.align,
                'ttype': line.field_id.ttype,
                'show_currency': line.show_currency,
            })
        return columns

    def _screen_cell(self, product, column, currency, price_unit):
        """One rendered cell of the suggestion list."""
        fname = column['name']
        # The price column must agree with what lands in the cart, so show the
        # pricelist price rather than the raw sales price.
        if fname in ('lst_price', 'list_price'):
            return formatLang(self.env, price_unit, currency_obj=currency)

        value = product[fname]
        ttype = column['ttype']
        if value is False or value is None or value == '':
            return ''
        if ttype == 'many2one':
            return value.display_name or ''
        if ttype == 'boolean':
            return _('Yes') if value else _('No')
        if ttype == 'selection':
            selection = dict(
                product._fields[fname]._description_selection(self.env))
            return selection.get(value, str(value))
        if ttype in ('float', 'monetary'):
            if column['show_currency'] or ttype == 'monetary':
                return formatLang(self.env, value, currency_obj=currency)
            return formatLang(self.env, value)
        if ttype == 'integer':
            return str(value)
        if ttype == 'date':
            return format_date(self.env, value)
        if ttype == 'datetime':
            return format_datetime(self.env, value)
        return str(value)

    @api.model
    def search_products(self, query='', limit=20, pricelist_id=False,
                        partner_id=False, company_id=False, config_id=False):
        """Type-ahead product lookup for the POS screen.

        Matches on internal reference, barcode and name. The columns shown
        come from the counter's configuration.
        """
        query = (query or '').strip()
        limit = min(max(int(limit or 20), 1), 50)
        company = self._screen_company(company_id)
        config = self._screen_config(config_id)
        partner = self.env['res.partner'].browse(partner_id) if partner_id \
            else self.env['res.partner']
        pricelist = self._screen_pricelist(pricelist_id, partner) \
            or config.pricelist_id
        currency = pricelist.currency_id or company.currency_id
        fiscal_position = self.env['account.fiscal.position'].with_company(
            company)._get_fiscal_position(partner) if partner else False

        domain = [
            ('sale_ok', '=', True),
            ('company_id', 'in', (False, company.id)),
        ]
        if config.product_domain_extra:
            try:
                domain += ast.literal_eval(config.product_domain_extra)
            except (ValueError, SyntaxError):
                raise UserError(_(
                    'The extra product filter on counter %s is not a valid '
                    'domain.', config.name))
        if query:
            domain += [
                '|', '|',
                ('default_code', 'ilike', query),
                ('barcode', 'ilike', query),
                ('name', 'ilike', query),
            ]

        products = self.env['product.product'].with_company(company).search(
            domain, limit=limit, order='default_code, name')
        if config.location_src_id:
            # On-hand should read as the stock at this counter, not company-wide.
            products = products.with_context(location=config.location_src_id.id)

        columns = self._screen_columns(config)
        results = []
        for product in products:
            taxes = self._screen_taxes(product, company, fiscal_position)
            price_unit = self._screen_price_unit(
                product, pricelist, 1.0, currency, partner)
            results.append({
                'id': product.id,
                'name': product.name,
                'display_name': product.display_name,
                'default_code': product.default_code or '',
                'uom_id': product.uom_id.id,
                'uom_name': product.uom_id.name or '',
                'tracks_stock': product.type == 'product',
                'qty_available': product.qty_available,
                'price_unit': price_unit,
                'tax_ids': taxes.ids,
                'tax_names': ', '.join(taxes.mapped('name')),
                'image_url': '/web/image/product.product/%s/image_128' % product.id,
                'cells': [
                    self._screen_cell(product, column, currency, price_unit)
                    for column in columns
                ],
            })
        return {
            'products': results,
            'columns': columns,
            'currency': self._currency_info(currency),
        }

    @api.model
    def search_partners(self, query='', limit=10):
        """Type-ahead customer lookup for the billing panel."""
        query = (query or '').strip()
        limit = min(max(int(limit or 10), 1), 30)
        domain = []
        if query:
            domain = ['|', '|', '|',
                      ('name', 'ilike', query),
                      ('ref', 'ilike', query),
                      ('phone', 'ilike', query),
                      ('mobile', 'ilike', query)]
        partners = self.env['res.partner'].search(domain, limit=limit)
        return [{
            'id': p.id,
            'name': p.name or '',
            'display_name': p.display_name,
            'city': p.city or '',
            'phone': p.mobile or p.phone or '',
            'pricelist_id': p.property_product_pricelist.id,
            'pricelist_name': p.property_product_pricelist.display_name or '',
        } for p in partners]

    @api.model
    def _normalize_phone(self, value):
        """Digits of a typed number, keeping a leading '+'. '' if not a number.

        Deliberately loose: the counter types numbers in all shapes
        (spaces, dashes, brackets). Real E.164 validation happens later,
        when the message is actually sent.
        """
        raw = (value or '').strip()
        if not raw:
            return ''
        plus = raw.startswith('+')
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if not 7 <= len(digits) <= 15:
            return ''
        # Anything other than digits and separators means it is a name.
        if any(ch.isalpha() for ch in raw):
            return ''
        return ('+' + digits) if plus else digits

    @api.model
    def find_or_create_partner_by_number(self, number):
        """Walk-in customer identified only by a phone number.

        Reuses an existing contact with that number so repeat customers do
        not pile up duplicates; otherwise creates one whose NAME IS THE
        NUMBER, which is what the counter types.
        """
        normalized = self._normalize_phone(number)
        if not normalized:
            raise UserError(_(
                '"%s" does not look like a phone number.', number))
        digits = normalized.lstrip('+')
        Partner = self.env['res.partner']

        # Match on the last 8 digits: the same person is often stored with
        # and without a country code.
        tail = digits[-8:]
        candidates = Partner.search(
            ['|', ('mobile', 'ilike', tail), ('phone', 'ilike', tail)])
        partner = candidates.filtered(lambda contact: digits in {
            self._normalize_phone(contact.mobile).lstrip('+'),
            self._normalize_phone(contact.phone).lstrip('+'),
        })[:1]
        created = not partner
        if created:
            partner = Partner.create({
                'name': normalized,
                'mobile': normalized,
                'company_type': 'person',
            })
        return {
            'id': partner.id,
            'name': partner.name or '',
            'display_name': partner.display_name,
            'city': partner.city or '',
            'phone': partner.mobile or partner.phone or '',
            'pricelist_id': partner.property_product_pricelist.id,
            'pricelist_name': partner.property_product_pricelist.display_name or '',
            'created': created,
        }

    @api.model
    def _currency_info(self, currency):
        currency = currency or self.env.company.currency_id
        return {
            'id': currency.id,
            'symbol': currency.symbol or '',
            'position': currency.position,
            'decimal_places': currency.decimal_places,
        }

    def _config_info(self, config):
        """Everything the screen needs about one counter."""
        currency = (config.pricelist_id.currency_id
                    or config.company_id.currency_id
                    or self.env.company.currency_id)
        return {
            'id': config.id,
            'name': config.name,
            'pricelist_id': config.pricelist_id.id,
            'pricelist_name': config.pricelist_id.display_name or '',
            'location_name': config.location_src_id.display_name or '',
            'deliver_on_payment': config.deliver_on_payment,
            'allow_negative_stock': config.allow_negative_stock,
            'columns': self._screen_columns(config),
            'currency': self._currency_info(currency),
            'receipt': {
                'paper': config.receipt_paper,
                'header': config.receipt_header or '',
                'footer': config.receipt_footer or '',
                'show_tax_breakup': config.receipt_show_tax_breakup,
                'auto_print': config.auto_print,
            },
            'payment_methods': [{
                'id': method.id,
                'name': method.name,
                'payment_type': method.payment_type,
                'machine_name': method.machine_name or '',
                'machine_code': method.machine_code or '',
                'is_cash': method.is_cash,
            } for method in config.payment_method_ids.sorted(
                lambda m: (m.sequence, m.name))],
        }

    @api.model
    def get_screen_config(self, company_id=False, config_id=False):
        """Start-up payload: the counters this cashier may use, plus the
        active counter's columns, payment methods and receipt settings."""
        company = self._screen_company(company_id)
        Config = self.env['pos.screen.config']
        configs = Config.search([
            ('company_id', '=', company.id),
            '|', ('user_ids', '=', False), ('user_ids', 'in', self.env.uid),
        ])
        active = Config.browse(config_id) if config_id and config_id in configs.ids \
            else (configs[:1] or Config)

        return {
            'company_id': company.id,
            'company_name': company.name,
            'company_address': ', '.join(part for part in [
                company.street, company.street2, company.city,
                company.zip, company.country_id.name] if part),
            'company_phone': company.phone or '',
            'company_vat': company.vat or '',
            'user_name': self.env.user.name,
            'currency': self._currency_info(company.currency_id),
            'configs': [{'id': c.id, 'name': c.name} for c in configs],
            'config': self._config_info(active) if active else False,
        }

    @api.model
    def compute_cart(self, payload):
        """Authoritative totals for the current cart.

        The screen owns the cart in memory; taxes are computed here so the
        displayed bill always matches what Odoo will store on save.
        """
        payload = payload or {}
        company = self._screen_company(payload.get('company_id'))
        partner = self.env['res.partner'].browse(payload['partner_id']) \
            if payload.get('partner_id') else self.env['res.partner']
        pricelist = self._screen_pricelist(payload.get('pricelist_id'), partner)
        currency = pricelist.currency_id or company.currency_id

        line_results = []
        tax_totals = {}
        amount_untaxed = 0.0
        amount_total = 0.0
        amount_gross = 0.0

        for line in payload.get('lines') or []:
            product = self.env['product.product'].browse(line.get('product_id'))
            if not product.exists():
                continue
            qty = float(line.get('qty') or 0.0)
            price_unit = float(line.get('price_unit') or 0.0)
            discount = float(line.get('discount') or 0.0)
            taxes = self.env['account.tax'].browse(line.get('tax_ids') or [])
            price = price_unit * (1.0 - discount / 100.0)
            computed = taxes.with_company(company).compute_all(
                price, currency=currency, quantity=qty,
                product=product, partner=partner or None)

            amount_untaxed += computed['total_excluded']
            amount_total += computed['total_included']

            # Same line without the discount, so the bill can show what the
            # customer saved. Run through compute_all as well, otherwise
            # price-included taxes would skew the gross.
            if discount:
                undiscounted = taxes.with_company(company).compute_all(
                    price_unit, currency=currency, quantity=qty,
                    product=product, partner=partner or None)
                amount_gross += undiscounted['total_excluded']
            else:
                amount_gross += computed['total_excluded']
            for tax in computed['taxes']:
                bucket = tax_totals.setdefault(
                    tax['id'], {'name': tax['name'], 'amount': 0.0})
                bucket['amount'] += tax['amount']

            line_results.append({
                'key': line.get('key'),
                'price_subtotal': computed['total_excluded'],
                'price_total': computed['total_included'],
                'price_tax': computed['total_included'] - computed['total_excluded'],
            })

        rounding = currency.round
        return {
            'lines': line_results,
            'amount_untaxed': rounding(amount_untaxed),
            'amount_tax': rounding(amount_total - amount_untaxed),
            'amount_total': rounding(amount_total),
            'amount_gross': rounding(amount_gross),
            'amount_discount': rounding(amount_gross - amount_untaxed),
            'tax_breakup': [
                {'id': tax_id, 'name': vals['name'],
                 'amount': rounding(vals['amount'])}
                for tax_id, vals in tax_totals.items()
            ],
            'currency': self._currency_info(currency),
        }

    @api.model
    def get_product_defaults(self, product_id, qty=1.0, pricelist_id=False,
                             partner_id=False, company_id=False):
        """Price / taxes / UoM to seed a newly added cart line."""
        company = self._screen_company(company_id)
        product = self.env['product.product'].with_company(company).browse(
            product_id)
        if not product.exists():
            raise UserError(_('This product no longer exists.'))
        partner = self.env['res.partner'].browse(partner_id) if partner_id \
            else self.env['res.partner']
        pricelist = self._screen_pricelist(pricelist_id, partner)
        currency = pricelist.currency_id or company.currency_id
        fiscal_position = self.env['account.fiscal.position'].with_company(
            company)._get_fiscal_position(partner) if partner else False
        taxes = self._screen_taxes(product, company, fiscal_position)
        return {
            'product_id': product.id,
            'name': product.display_name,
            'uom_id': product.uom_id.id,
            'uom_name': product.uom_id.name or '',
            'qty_available': product.qty_available,
            'tracks_stock': product.type == 'product',
            'price_unit': self._screen_price_unit(
                product, pricelist, qty, currency, partner),
            'tax_ids': taxes.ids,
            'tax_names': ', '.join(taxes.mapped('name')),
            'image_url': '/web/image/product.product/%s/image_128' % product.id,
        }

    @api.model
    def refresh_cart_pricing(self, payload):
        """Re-price every cart line after the customer or pricelist changed.

        Returned in one round trip so the screen does not fire one call per
        line.
        """
        payload = payload or {}
        company = self._screen_company(payload.get('company_id'))
        partner = self.env['res.partner'].browse(payload['partner_id']) \
            if payload.get('partner_id') else self.env['res.partner']
        pricelist = self._screen_pricelist(payload.get('pricelist_id'), partner)
        currency = pricelist.currency_id or company.currency_id
        fiscal_position = self.env['account.fiscal.position'].with_company(
            company)._get_fiscal_position(partner) if partner else False

        updates = []
        for line in payload.get('lines') or []:
            product = self.env['product.product'].with_company(company).browse(
                line.get('product_id'))
            if not product.exists():
                continue
            taxes = self._screen_taxes(product, company, fiscal_position)
            updates.append({
                'key': line.get('key'),
                'price_unit': self._screen_price_unit(
                    product, pricelist, float(line.get('qty') or 1.0),
                    currency, partner),
                'tax_ids': taxes.ids,
                'tax_names': ', '.join(taxes.mapped('name')),
            })
        return updates

    @api.model
    def _prepare_order_vals(self, payload):
        """Values written when the screen saves a bill.

        Override point for bridge modules that add their own fields; it runs
        BEFORE confirm/pay, so anything set here is in place by the time the
        payment hooks fire.
        """
        company = self._screen_company(payload.get('company_id'))
        config = self._screen_config(payload.get('config_id'))
        if not config or config.company_id != company:
            raise UserError(_('Select an available counter belonging to the bill company.'))
        return {
            'company_id': company.id,
            'partner_id': payload.get('partner_id') or False,
            'pricelist_id': payload.get('pricelist_id') or False,
            'config_id': config.id,
            'payment_method_id': payload.get('payment_method_id') or False,
            'note': payload.get('note') or False,
            'line_ids': [(5, 0, 0)] + [
                (0, 0, self._prepare_line_vals(line))
                for line in (payload.get('lines') or [])
            ],
        }

    @api.model
    def create_from_ui(self, payload):
        """Persist the cart as a ``pos.screen.order``.

        ``payload['order_id']`` updates an existing draft instead of
        creating a new one, so the screen can be reopened and edited.
        """
        payload = payload or {}
        lines = payload.get('lines') or []
        if not lines:
            raise UserError(_('Add at least one product before saving.'))

        vals = self._prepare_order_vals(payload)

        order = self.browse(payload.get('order_id')) if payload.get('order_id') \
            else self.browse()
        if order and order.exists():
            paying_confirmed = order.state == 'confirmed' and payload.get('paid')
            if order.state != 'draft' and not paying_confirmed:
                raise UserError(_(
                    '%s is no longer a draft and cannot be changed from the '
                    'screen.', order.name))
            if not paying_confirmed:
                order.write(vals)
        else:
            order = self.create(vals)

        if payload.get('confirm') and order.state == 'draft':
            order.action_confirm()
        if payload.get('paid'):
            order.action_mark_paid()

        return {
            'order_id': order.id,
            'name': order.name,
            'state': order.state,
            'amount_untaxed': order.amount_untaxed,
            'amount_tax': order.amount_tax,
            'amount_total': order.amount_total,
            'picking_name': order.picking_id.name or '',
        }

    @api.model
    def _prepare_line_vals(self, line):
        product = self.env['product.product'].browse(line.get('product_id'))
        if not product.exists():
            raise UserError(_('One of the cart products no longer exists.'))
        qty = float(line.get('qty') or 0.0)
        if qty <= 0:
            raise UserError(_(
                'Set a quantity for %s, or remove it from the bill.',
                product.display_name))
        return {
            'product_id': product.id,
            'name': line.get('name') or product.display_name,
            'product_uom_id': line.get('uom_id') or product.uom_id.id,
            'qty': qty,
            'price_unit': float(line.get('price_unit') or 0.0),
            'discount': float(line.get('discount') or 0.0),
            'tax_ids': [(6, 0, line.get('tax_ids') or [])],
        }

    @api.model
    def get_draft_orders(self, limit=20):
        """Parked bills the cashier can pick back up.

        Record rules already scope this: a cashier sees only their own
        drafts, a manager sees everyone's.
        """
        limit = min(max(int(limit or 20), 1), 50)
        orders = self.search([('state', '=', 'draft')], limit=limit)
        return [{
            'id': order.id,
            'name': order.name,
            'date_order': order.date_order,
            'partner_name': order.partner_id.display_name or '',
            'user_name': order.user_id.name or '',
            'line_count': order.line_count,
            'amount_total': order.amount_total,
            'currency_id': order.currency_id.id,
        } for order in orders]

    @api.model
    def load_order(self, order_id):
        """Read an existing order back into the screen's cart shape."""
        order = self.browse(order_id)
        if not order.exists():
            raise UserError(_('This order no longer exists.'))
        return {
            'order_id': order.id,
            'name': order.name,
            'state': order.state,
            'date_order': order.date_order,
            'partner_id': order.partner_id.id,
            'partner_name': order.partner_id.display_name or '',
            'pricelist_id': order.pricelist_id.id,
            'pricelist_name': order.pricelist_id.display_name or '',
            'config_id': order.config_id.id,
            'payment_method_id': order.payment_method_id.id,
            'note': order.note or '',
            'company_id': order.company_id.id,
            'currency': self._currency_info(order.currency_id),
            'lines': [{
                'product_id': line.product_id.id,
                'name': line.name or '',
                'default_code': line.product_id.default_code or '',
                'uom_id': line.product_uom_id.id,
                'uom_name': line.product_uom_id.name or '',
                'qty': line.qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': line.tax_ids.ids,
                'tax_names': ', '.join(line.tax_ids.mapped('name')),
                'qty_available': line.product_id.qty_available,
                'tracks_stock': line.product_id.type == 'product',
                'image_url': '/web/image/product.product/%s/image_128' % line.product_id.id,
            } for line in order.line_ids],
        }


class PosScreenOrderLine(models.Model):
    _name = 'pos.screen.order.line'
    _description = 'Velkio Easy POS Order Line'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one(
        'pos.screen.order', string='Order', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        related='order_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='order_id.currency_id', store=True, readonly=True)
    state = fields.Selection(related='order_id.state', store=True, readonly=True)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain="[('sale_ok', '=', True)]")
    name = fields.Char(string='Description')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    qty = fields.Float(
        string='Quantity', digits='Product Unit of Measure', default=1.0,
        required=True)
    price_unit = fields.Float(
        string='Unit Price', digits='Product Price', default=0.0)
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    tax_ids = fields.Many2many(
        'account.tax', string='Taxes', check_company=True,
        domain="[('type_tax_use', '=', 'sale')]")

    price_subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_amounts', store=True)
    price_tax = fields.Monetary(
        string='Tax Amount', compute='_compute_amounts', store=True)
    price_total = fields.Monetary(
        string='Total', compute='_compute_amounts', store=True)

    _sql_constraints = [
        ('qty_positive', 'CHECK(qty > 0)',
         'Bill quantities must be positive. Returns require a separate stock return.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env['pos.screen.order'].browse(vals.get('order_id'))
            if order.state != 'draft':
                raise UserError(_('Items can only be added to draft bills.'))
            if not vals.get('name'):
                vals['name'] = self.env['product.product'].browse(vals.get('product_id')).display_name
        return super().create(vals_list)

    def write(self, vals):
        orders = self.order_id | self.env['pos.screen.order'].browse(vals.get('order_id'))
        if any(order.state != 'draft' for order in orders):
            raise UserError(_('Items can only be changed on draft bills.'))
        return super().write(vals)

    def unlink(self):
        if any(line.order_id.state not in ('draft', 'cancel') for line in self):
            raise UserError(_('Items cannot be removed from confirmed or paid bills.'))
        return super().unlink()

    @api.constrains('qty', 'price_unit', 'discount', 'product_uom_id', 'product_id')
    def _check_line_values(self):
        for line in self:
            if not all(math.isfinite(v) for v in (line.qty, line.price_unit, line.discount)) or line.qty <= 0 or line.price_unit < 0:
                raise ValidationError(_('Use a positive finite quantity and a non-negative finite price.'))
            if line.product_uom_id and line.product_uom_id.category_id != line.product_id.uom_id.category_id:
                raise ValidationError(_('The bill unit of measure must match the product category.'))

    @api.constrains('discount')
    def _check_discount(self):
        for line in self:
            if line.discount < 0.0 or line.discount > 100.0:
                raise ValidationError(_(
                    'Discount on %s must be between 0 and 100.',
                    line.product_id.display_name))

    @api.depends('qty', 'price_unit', 'discount', 'tax_ids', 'product_id',
                 'order_id.partner_id', 'currency_id')
    def _compute_amounts(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            computed = line.tax_ids.with_company(
                line.company_id or self.env.company).compute_all(
                    price, currency=currency, quantity=line.qty,
                    product=line.product_id,
                    partner=line.order_id.partner_id or None)
            line.price_subtotal = computed['total_excluded']
            line.price_total = computed['total_included']
            line.price_tax = computed['total_included'] - computed['total_excluded']

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            product = line.product_id
            if not product:
                continue
            order = line.order_id
            defaults = self.env['pos.screen.order'].get_product_defaults(
                product.id, qty=line.qty or 1.0,
                pricelist_id=order.pricelist_id.id,
                partner_id=order.partner_id.id,
                company_id=order.company_id.id)
            line.name = defaults['name']
            line.product_uom_id = defaults['uom_id']
            line.price_unit = defaults['price_unit']
            line.tax_ids = [(6, 0, defaults['tax_ids'])]
