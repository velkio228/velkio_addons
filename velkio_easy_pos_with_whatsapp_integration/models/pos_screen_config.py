# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Field types the search list knows how to render. Anything else (binary,
# one2many, ...) would not fit a compact suggestion row.
SUPPORTED_COLUMN_TYPES = (
    'char', 'text', 'integer', 'float', 'monetary',
    'boolean', 'selection', 'many2one', 'date', 'datetime',
)

# name, label, width, align, show as currency
DEFAULT_COLUMNS = [
    ('default_code', 'CODE', 110, 'left', False),
    ('name', 'PRODUCT', 0, 'left', False),
    ('qty_available', 'ON HAND', 90, 'right', False),
    ('uom_id', 'UOM', 70, 'left', False),
    ('lst_price', 'PRICE', 110, 'right', True),
]


class PosScreenConfig(models.Model):
    _name = 'pos.screen.config'
    _description = 'Velkio Easy POS Counter'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(string='Counter', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    user_ids = fields.Many2many(
        'res.users', string='Allowed Cashiers',
        help='Leave empty to let every POS user bill from this counter.')

    # ---------------- stock ----------------
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Operation Type', check_company=True,
        domain="[('code', '=', 'outgoing')]",
        help='Delivery operation used when a bill is paid.')
    location_src_id = fields.Many2one(
        'stock.location', string='Stock Location', check_company=True,
        domain="[('usage', '=', 'internal')]",
        help='Location the sold goods are taken from.')
    location_dest_id = fields.Many2one(
        'stock.location', string='Customer Location', check_company=True,
        domain="[('usage', 'in', ('customer', 'inventory', 'production'))]",
        help='Counterpart location the goods are delivered to.')
    deliver_on_payment = fields.Boolean(
        string='Deliver on Payment', default=True,
        help='Create and validate the delivery as soon as the bill is paid, '
             'so on-hand quantities drop immediately.')
    allow_negative_stock = fields.Boolean(
        string='Allow Billing Without Stock', default=True,
        help='Uncheck to block paying a bill when a storable product does not '
             'have enough quantity on hand at the counter location.')

    # ---------------- pricing ----------------
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Default Pricelist', check_company=True)
    product_domain_extra = fields.Char(
        string='Extra Product Filter',
        help="Optional domain appended to the product search, e.g. "
             "[('categ_id', 'child_of', 5)].")

    # ---------------- search columns ----------------
    search_field_ids = fields.One2many(
        'pos.screen.config.field', 'config_id', string='Search Columns',
        copy=True)

    # ---------------- payment ----------------
    payment_method_ids = fields.Many2many(
        'pos.screen.payment.method', string='Payment Methods',
        check_company=True)

    # ---------------- receipt ----------------
    receipt_paper = fields.Selection(
        [('80', '80 mm Thermal'), ('58', '58 mm Thermal'), ('a4', 'A4')],
        string='Receipt Size', default='80', required=True)
    receipt_header = fields.Text(string='Receipt Header')
    receipt_footer = fields.Text(
        string='Receipt Footer', default='Thank you, visit again!')
    receipt_show_tax_breakup = fields.Boolean(
        string='Print Tax Breakup', default=True)
    auto_print = fields.Boolean(
        string='Print Automatically on Payment', default=False)

    _sql_constraints = [
        ('name_company_uniq', 'UNIQUE(name, company_id)',
         'A counter with this name already exists for this company.'),
    ]

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        for config in self:
            picking_type = config.picking_type_id
            if not picking_type:
                continue
            config.location_src_id = (
                picking_type.default_location_src_id
                or config.location_src_id)
            config.location_dest_id = (
                picking_type.default_location_dest_id
                or config.location_dest_id)

    @api.constrains('deliver_on_payment', 'picking_type_id',
                    'location_src_id', 'location_dest_id')
    def _check_stock_setup(self):
        for config in self:
            if not config.deliver_on_payment:
                continue
            missing = [
                label for label, value in (
                    (_('Operation Type'), config.picking_type_id),
                    (_('Stock Location'), config.location_src_id),
                    (_('Customer Location'), config.location_dest_id),
                ) if not value
            ]
            if missing:
                raise ValidationError(_(
                    'Counter %(name)s delivers on payment, so it needs: '
                    '%(missing)s.',
                    name=config.name, missing=', '.join(missing)))

    @api.model_create_multi
    def create(self, vals_list):
        configs = super().create(vals_list)
        # A counter with no columns would show a blank suggestion list.
        for config in configs:
            if not config.search_field_ids:
                config._apply_default_columns()
        return configs

    def _apply_default_columns(self):
        """Seed the search list with a sensible set of columns."""
        self.ensure_one()
        Field = self.env['ir.model.fields']
        lines = []
        for sequence, (fname, label, width, align, money) in enumerate(
                DEFAULT_COLUMNS, start=1):
            field = Field._get('product.product', fname)
            if not field:
                continue
            lines.append((0, 0, {
                'sequence': sequence * 10,
                'field_id': field.id,
                'label': label,
                'width': width,
                'align': align,
                'show_currency': money,
            }))
        if lines:
            self.search_field_ids = lines

    def action_reset_columns(self):
        for config in self:
            config.search_field_ids.unlink()
            config._apply_default_columns()
        return True

    @api.model
    def _default_config(self):
        """The counter to use when the screen does not name one."""
        domain = [('company_id', '=', self.env.company.id)]
        allowed = self.search(
            domain + ['|', ('user_ids', '=', False),
                      ('user_ids', 'in', self.env.uid)], limit=1)
        return allowed


class PosScreenConfigField(models.Model):
    _name = 'pos.screen.config.field'
    _description = 'Velkio Easy POS Search Column'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'pos.screen.config', string='Counter', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    field_id = fields.Many2one(
        'ir.model.fields', string='Product Field', required=True,
        ondelete='cascade',
        domain="[('model', '=', 'product.product'),"
               " ('ttype', 'in', %s)]" % str(list(SUPPORTED_COLUMN_TYPES)))
    field_name = fields.Char(
        related='field_id.name', string='Technical Name', store=True)
    label = fields.Char(
        string='Column Label',
        help='Leave empty to use the field label.')
    width = fields.Integer(
        string='Width (px)', default=0,
        help='0 lets the column take the remaining space.')
    align = fields.Selection(
        [('left', 'Left'), ('right', 'Right'), ('center', 'Center')],
        string='Align', default='left', required=True)
    show_currency = fields.Boolean(
        string='Show as Amount',
        help='Format this column as money. Tick it for price fields: a price '
             'is stored as a plain float, so it is not formatted as currency '
             'otherwise.')

    _sql_constraints = [
        ('field_uniq', 'UNIQUE(config_id, field_id)',
         'This field is already shown in the search list.'),
    ]

    @api.constrains('field_id')
    def _check_field(self):
        for line in self:
            field = line.field_id
            if field.model != 'product.product':
                raise ValidationError(_(
                    'Search columns must be fields of Product, not %s.',
                    field.model))
            if field.ttype not in SUPPORTED_COLUMN_TYPES:
                raise ValidationError(_(
                    'The search list cannot display "%(label)s" (%(ttype)s '
                    'fields are not supported).',
                    label=field.field_description, ttype=field.ttype))

    @api.onchange('field_id')
    def _onchange_field_id(self):
        for line in self:
            if line.field_id and not line.label:
                line.label = line.field_id.field_description


class PosScreenPaymentMethod(models.Model):
    _name = 'pos.screen.payment.method'
    _description = 'Velkio Easy POS Payment Method'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(string='Payment Method', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    payment_type = fields.Selection(
        [('cash', 'Cash'), ('card', 'Card'), ('upi', 'UPI'),
         ('bank', 'Bank Transfer'), ('cheque', 'Cheque'),
         ('credit', 'Credit / On Account')],
        string='Type', default='cash', required=True)
    machine_name = fields.Char(
        string='Machine / Terminal',
        help='Card swipe machine, UPI QR or counter drawer this method uses. '
             'Recorded on the bill so takings can be reconciled per machine.')
    machine_code = fields.Char(string='Machine ID')
    journal_id = fields.Many2one(
        'account.journal', string='Journal', check_company=True,
        help='Accounting journal these takings belong to.')
    is_cash = fields.Boolean(
        string='Cash Drawer', compute='_compute_is_cash', store=True)
    note = fields.Char(string='Note')

    _sql_constraints = [
        ('name_company_uniq', 'UNIQUE(name, company_id)',
         'A payment method with this name already exists for this company.'),
    ]

    @api.depends('payment_type')
    def _compute_is_cash(self):
        for method in self:
            method.is_cash = method.payment_type == 'cash'

    @api.depends('name', 'machine_name')
    def _compute_display_name(self):
        for method in self:
            method.display_name = (
                '%s (%s)' % (method.name, method.machine_name)
                if method.machine_name else method.name)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    pos_screen_order_ids = fields.One2many(
        'pos.screen.order', 'picking_id', string='POS Bills')
