import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from odoo.tools import frozendict

_logger = logging.getLogger(__name__)

MODES = ('read', 'write', 'create', 'unlink')

# Switches of the profile that apply to every model ("Global" tab and the two
# checkboxes above the tabs).
GLOBAL_FLAGS = (
    'readonly', 'disable_relational_edit', 'disable_debug', 'disable_login',
    'hide_chatter', 'hide_send_message', 'hide_log_note', 'hide_activity',
    'hide_import', 'hide_export', 'hide_spreadsheet', 'hide_add_property',
)
# One rule list per tab of the Access Rights screen.
LINE_FIELDS = {
    'model_line_ids': 'zenvio.access.profile.model',
    'field_line_ids': 'zenvio.access.profile.field',
    'domain_line_ids': 'zenvio.access.profile.domain',
    'button_line_ids': 'zenvio.access.profile.button',
    'filter_line_ids': 'zenvio.access.profile.filter',
    'chatter_line_ids': 'zenvio.access.profile.chatter',
}
# Labels of the profile's fields, reused for the per-role copies on the department.
FIELD_LABELS = {
    'readonly': 'Read-Only', 'disable_relational_edit': 'Disable Relational Create/Edit',
    'disable_debug': 'Disable Developer Mode', 'disable_login': 'Disable Login',
    'hide_chatter': 'Hide Chatter', 'hide_send_message': 'Hide Send Message', 'hide_log_note': 'Hide Log Notes',
    'hide_activity': 'Hide Schedule Activity', 'hide_import': 'Hide Import', 'hide_export': 'Hide Export',
    'hide_spreadsheet': 'Hide Spreadsheet', 'hide_add_property': 'Hide Add Property', 'hide_menu_ids': 'Hidden Menus',
    'model_line_ids': 'Model Access', 'field_line_ids': 'Field Access', 'domain_line_ids': 'Domain Access',
    'button_line_ids': 'Button/Tab Access', 'filter_line_ids': 'Hide Filter/Group By', 'chatter_line_ids': 'Chatter',
}
# Per-model switches of the Model Access and Chatter tabs.
MODEL_FLAGS = ('hide_archive', 'hide_duplicate', 'hide_import', 'hide_export', 'hide_print', 'hide_actions')
CHATTER_FLAGS = ('hide_chatter', 'hide_send_message', 'hide_log_note', 'hide_activity')


class ZenvioAccessProfile(models.Model):
    """What an employee logged in through a department may do.

    An employee works as their Top Management user; the profile only takes
    rights away (menus, models, records, fields, buttons, tabs, filters,
    chatter, import/export ...), it can never give more than that user has.
    Profiles are used per department role, or for a single employee.
    """
    _name = 'zenvio.access.profile'
    _description = 'Department Access Profile'
    _order = 'name, id'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    owner_id = fields.Many2one(
        'res.users', string='Top Management', required=True, index=True, ondelete='cascade',
        default=lambda self: self.env.user,
        help="Top Management user whose employees use this profile.")
    note = fields.Text()

    readonly = fields.Boolean(
        string='Read-Only',
        help="The employee can look at everything allowed but cannot create, change or delete anything.")
    disable_relational_edit = fields.Boolean(
        string='Disable Relational Create/Edit',
        help="In linked fields (e.g. Customer, Product) the employee cannot create, edit or open the linked record.")
    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', 'zenvio_access_profile_menu_rel', 'profile_id', 'menu_id', string='Hidden Menus',
        help="Menus (and their sub-menus) the employee does not see.")

    hide_chatter = fields.Boolean(string='Hide Chatter', help="No chatter on any form.")
    hide_send_message = fields.Boolean(string='Hide Send Message', help="Cannot send messages to followers anywhere.")
    hide_log_note = fields.Boolean(string='Hide Log Notes', help="Cannot log internal notes anywhere.")
    hide_activity = fields.Boolean(string='Hide Schedule Activity', help="Cannot schedule activities anywhere.")
    hide_import = fields.Boolean(string='Hide Import', help="Cannot import records anywhere.")
    hide_export = fields.Boolean(string='Hide Export', help="Cannot export records anywhere.")
    hide_spreadsheet = fields.Boolean(string='Hide Spreadsheet', help="No 'Insert in spreadsheet'.")
    hide_add_property = fields.Boolean(string='Hide Add Property', help="Cannot add custom properties to records.")
    disable_login = fields.Boolean(
        string='Disable Login', help="Employees with this access cannot log in; open sessions end.")
    disable_debug = fields.Boolean(
        string='Disable Developer Mode', help="Developer mode (?debug=1) is switched off for these employees.")

    model_line_ids = fields.One2many('zenvio.access.profile.model', 'profile_id', string='Model Access', copy=True)
    field_line_ids = fields.One2many('zenvio.access.profile.field', 'profile_id', string='Field Access', copy=True)
    domain_line_ids = fields.One2many('zenvio.access.profile.domain', 'profile_id', string='Domain Access', copy=True)
    button_line_ids = fields.One2many('zenvio.access.profile.button', 'profile_id', string='Button/Tab Access', copy=True)
    filter_line_ids = fields.One2many('zenvio.access.profile.filter', 'profile_id', string='Hide Filter/Group By', copy=True)
    chatter_line_ids = fields.One2many('zenvio.access.profile.chatter', 'profile_id', string='Chatter', copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        self.env.registry.clear_cache()
        return profiles

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    @api.model
    @tools.ormcache('profile_id')
    def _zenvio_rules(self, profile_id):
        """Everything the security hooks need, read once per profile and kept
        until a profile, rule or employee mapping changes."""
        profile = self.sudo().browse(profile_id).exists()
        if not profile or not profile.active:
            return None
        rules = {}

        def rule_of(model_name):
            return rules.setdefault(model_name, {
                'denied': set(), 'domains': [], 'buttons': {}, 'pages': {}, 'invisible': {},
                'readonly_fields': {}, 'required_fields': {}, 'no_open_fields': set(), 'filters': set(),
                'state_fields': set(), **dict.fromkeys(MODEL_FLAGS + CHATTER_FLAGS, False),
            })

        for line in profile.model_line_ids:
            rule = rule_of(line.model_name)
            rule['denied'].update(mode for mode in MODES if not line[f'perm_{mode}'])
            for flag in MODEL_FLAGS:
                rule[flag] |= line[flag]
        for line in profile.domain_line_ids:
            if line.domain and line.domain.strip() not in ('', '[]'):
                rule_of(line.model_name)['domains'].append(line.domain)
        for line in profile.field_line_ids:
            rule, cond = rule_of(line.model_name), line._state_condition()
            for field in line.field_ids:
                for flag, key in (('invisible', 'invisible'), ('readonly', 'readonly_fields'), ('required', 'required_fields')):
                    if line[flag]:
                        rule[key].setdefault(field.name, []).append(cond)
                if line.no_open:
                    rule['no_open_fields'].add(field.name)
            if cond != '1':
                rule['state_fields'].add(line.state_field_name)
        for line in profile.button_line_ids:
            rule, cond = rule_of(line.model_name), line._state_condition()
            for node in line.hide_button_ids:
                rule['buttons'].setdefault(node.attr_name, []).append((line.state_field_name, line._state_values()))
            for node in line.hide_page_ids:
                rule['pages'].setdefault((node.attr_name or '', node.attr_string), []).append(cond)
            if cond != '1':
                rule['state_fields'].add(line.state_field_name)
        for line in profile.filter_line_ids:
            rule_of(line.model_name)['filters'].update((line.hide_filter_ids | line.hide_groupby_ids).mapped('attr_name'))
        for line in profile.chatter_line_ids:
            rule = rule_of(line.model_name)
            for flag in CHATTER_FLAGS:
                rule[flag] |= line[flag]

        for rule in rules.values():
            for key in ('denied', 'no_open_fields', 'filters', 'state_fields'):
                rule[key] = frozenset(rule[key])
            rule['domains'] = tuple(rule['domains'])
        dates = [profile.write_date]
        for fname in LINE_FIELDS:
            dates += profile[fname].mapped('write_date')
        hidden_menus = self.env['ir.ui.menu'].sudo().search([('id', 'child_of', profile.hide_menu_ids.ids)])
        return frozendict({
            'id': profile.id,
            'version': str(max(dates)),
            'hidden_menu_ids': frozenset(hidden_menus.ids),
            'models': frozendict({name: frozendict(rule) for name, rule in rules.items()}),
            **{flag: profile[flag] for flag in GLOBAL_FLAGS},
        })


class ZenvioAccessProfileLine(models.AbstractModel):
    """Common part of the rule lists: a model inside a profile."""
    _name = 'zenvio.access.profile.line'
    _description = 'Department Access Profile - Rule'
    _order = 'profile_id, id'

    profile_id = fields.Many2one('zenvio.access.profile', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade',
                               domain=[('transient', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True, string='Model Technical Name')

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if self.model_id:
            self.env['zenvio.access.view.node']._sync_nodes(self.model_id)

    def _sync_helpers(self):
        for model in self.model_id:
            self.env['zenvio.access.view.node']._sync_nodes(model)
        if 'state_field_id' in self._fields:  # rules with a state condition
            for field in self.state_field_id:
                self.env['zenvio.access.state.value']._sync_values(field)

    def action_sync_helpers(self):
        self._sync_helpers()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_helpers()
        self.env.registry.clear_cache()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'model_id', 'state_field_id'} & set(vals):
            self._sync_helpers()
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res


class ZenvioAccessProfileStateMixin(models.AbstractModel):
    """Limit a screen rule to some states (stages) of the record."""
    _name = 'zenvio.access.profile.state.mixin'
    _description = 'Department Access Profile - State Condition'

    state_field_id = fields.Many2one(
        'ir.model.fields', string='State Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['selection', 'many2one']), ('store', '=', True)]",
        help="Field holding the record's stage or status, to apply the rule only in some states.")
    state_field_name = fields.Char(related='state_field_id.name', store=True)
    state_field_ttype = fields.Selection(related='state_field_id.ttype')
    state_value_ids = fields.Many2many(
        'zenvio.access.state.value', string='Only In States', domain="[('field_id', '=', state_field_id)]",
        help="The rule applies only in these states. Empty: in every state.")

    @api.constrains('state_field_id', 'model_id')
    def _check_state_field(self):
        for line in self:
            if line.state_field_id and line.state_field_id.model_id != line.model_id:
                raise ValidationError(_('The state field must belong to the selected model.'))

    @api.onchange('model_id')
    def _onchange_model_state(self):
        self.state_field_id = self.env['ir.model.fields'].search([
            ('model_id', '=', self.model_id.id), ('name', '=', 'state'), ('ttype', '=', 'selection')], limit=1)

    @api.onchange('state_field_id')
    def _onchange_state_field_id(self):
        self.state_value_ids = False
        if self.state_field_id:
            self.env['zenvio.access.state.value']._sync_values(self.state_field_id)

    def _state_values(self):
        """Python values of the selected states (empty tuple: every state)."""
        self.ensure_one()
        if not self.state_field_name or not self.state_value_ids:
            return ()
        if self.state_field_ttype == 'many2one':
            return tuple(int(v.value_key) for v in self.state_value_ids if v.value_key.isdigit()) or (0,)
        return tuple(self.state_value_ids.mapped('value_key'))

    def _state_condition(self):
        """View expression that is true when the rule applies ('1' = always)."""
        values = self._state_values()
        if not values:
            return '1'
        return '%s in %r' % (self.state_field_name, list(values))


class ZenvioAccessProfileModel(models.Model):
    """Model Access: what the employee may do with a model's records."""
    _name = 'zenvio.access.profile.model'
    _inherit = 'zenvio.access.profile.line'
    _description = 'Department Access Profile - Model Access'

    _profile_model_uniq = models.Constraint(
        'UNIQUE(profile_id, model_id)',
        'Each model can only have one Model Access line per profile.',
    )

    perm_read = fields.Boolean(string='Read', default=True)
    perm_create = fields.Boolean(string='Create', default=True)
    perm_write = fields.Boolean(string='Edit', default=True)
    perm_unlink = fields.Boolean(string='Delete', default=True)
    hide_archive = fields.Boolean(string='Hide Archive/Unarchive')
    hide_duplicate = fields.Boolean(string='Hide Duplicate')
    hide_import = fields.Boolean(string='Hide Import')
    hide_export = fields.Boolean(string='Hide Export')
    hide_print = fields.Boolean(string='Hide Reports', help="No Print menu (reports) on this model.")
    hide_actions = fields.Boolean(string='Hide Actions', help="No server actions in the Actions menu of this model.")

    @api.constrains('perm_read', 'perm_create', 'perm_write', 'perm_unlink')
    def _check_perms(self):
        for line in self:
            if not line.perm_read and (line.perm_create or line.perm_write or line.perm_unlink):
                raise ValidationError(_(
                    "%(model)s: an employee who cannot read records cannot create, edit or delete them either.",
                    model=line.model_id.name))

    @api.onchange('perm_read')
    def _onchange_perm_read(self):
        if not self.perm_read:
            self.perm_create = self.perm_write = self.perm_unlink = False


class ZenvioAccessProfileField(models.Model):
    """Field Access: hide, lock or require fields of a model."""
    _name = 'zenvio.access.profile.field'
    _inherit = ['zenvio.access.profile.line', 'zenvio.access.profile.state.mixin']
    _description = 'Department Access Profile - Field Access'

    field_ids = fields.Many2many(
        'ir.model.fields', 'zenvio_access_profile_field_rel', 'line_id', 'field_id',
        string='Fields', required=True, domain="[('model_id', '=', model_id)]")
    invisible = fields.Boolean(string='Invisible')
    readonly = fields.Boolean(string='Read-Only')
    required = fields.Boolean(string='Required')
    no_open = fields.Boolean(
        string='Remove External Link', help="Linked fields: no create, edit or open of the linked record.")

    @api.constrains('invisible', 'readonly', 'required', 'no_open')
    def _check_something(self):
        for line in self:
            if not (line.invisible or line.readonly or line.required or line.no_open):
                raise ValidationError(_("%s: tick at least one of Invisible, Read-Only, Required or Remove External Link.",
                                        line.model_id.name))


class ZenvioAccessProfileDomain(models.Model):
    """Domain Access: the records of a model the employee may see and change."""
    _name = 'zenvio.access.profile.domain'
    _inherit = 'zenvio.access.profile.line'
    _description = 'Department Access Profile - Domain Access'

    domain = fields.Char(
        string='Only These Records', default='[]', required=True,
        help="The employee only sees and changes the records matching this filter. "
             "You can use employee (the logged-in employee), department and user.")


class ZenvioAccessProfileButton(models.Model):
    """Button/Tab Access: hide buttons and notebook tabs of a model."""
    _name = 'zenvio.access.profile.button'
    _inherit = ['zenvio.access.profile.line', 'zenvio.access.profile.state.mixin']
    _description = 'Department Access Profile - Button/Tab Access'

    hide_button_ids = fields.Many2many(
        'zenvio.access.view.node', 'zenvio_access_button_rule_button_rel', 'line_id', 'node_id',
        string='Hidden Buttons', domain="[('model_id', '=', model_id), ('node_type', '=', 'button')]",
        help="Hidden on screen, and refused on the server if someone calls them anyway.")
    hide_page_ids = fields.Many2many(
        'zenvio.access.view.node', 'zenvio_access_button_rule_page_rel', 'line_id', 'node_id',
        string='Hidden Tabs', domain="[('model_id', '=', model_id), ('node_type', '=', 'page')]")


class ZenvioAccessProfileFilter(models.Model):
    """Hide Filter/Group By: options removed from a model's search panel."""
    _name = 'zenvio.access.profile.filter'
    _inherit = 'zenvio.access.profile.line'
    _description = 'Department Access Profile - Hide Filter/Group By'

    hide_filter_ids = fields.Many2many(
        'zenvio.access.view.node', 'zenvio_access_filter_rule_filter_rel', 'line_id', 'node_id',
        string='Hidden Filters', domain="[('model_id', '=', model_id), ('node_type', '=', 'filter')]")
    hide_groupby_ids = fields.Many2many(
        'zenvio.access.view.node', 'zenvio_access_filter_rule_groupby_rel', 'line_id', 'node_id',
        string='Hidden Group By', domain="[('model_id', '=', model_id), ('node_type', '=', 'groupby')]")


class ZenvioAccessProfileChatter(models.Model):
    """Chatter: hide the chatter, or some of its actions, on a model."""
    _name = 'zenvio.access.profile.chatter'
    _inherit = 'zenvio.access.profile.line'
    _description = 'Department Access Profile - Chatter'

    hide_chatter = fields.Boolean(string='Hide Chatter')
    hide_send_message = fields.Boolean(string='Hide Send Message')
    hide_log_note = fields.Boolean(string='Hide Log Notes')
    hide_activity = fields.Boolean(string='Hide Schedule Activity')


class ZenvioAccessViewNode(models.Model):
    """Buttons, tabs, filters and group-bys found in a model's views, so they
    can be picked by label."""
    _name = 'zenvio.access.view.node'
    _description = 'Department Access Profile - View Node'
    _order = 'node_type, attr_string, id'
    _rec_name = 'display_label'

    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade', index=True)
    node_type = fields.Selection(
        [('page', 'Tab'), ('button', 'Button'), ('filter', 'Filter'), ('groupby', 'Group By')],
        string='Type', required=True)
    attr_name = fields.Char('Technical Name')
    attr_string = fields.Char('Label', required=True)
    is_smart = fields.Boolean('Smart Button')
    display_label = fields.Char(compute='_compute_display_label', store=True)

    @api.depends('attr_string', 'attr_name', 'is_smart')
    def _compute_display_label(self):
        for node in self:
            label = node.attr_string or ''
            if node.attr_name:
                label += ' (%s)' % node.attr_name
            if node.is_smart:
                label += ' [Smart]'
            node.display_label = label

    @api.model
    def _node_label(self, node):
        label = node.get('string') or ' '.join(t.strip() for t in node.xpath('.//text()') if t.strip())
        return label.strip()[:120]

    @api.model
    def _sync_nodes(self, model):
        """Add the buttons and tabs of ``model``'s form, list and kanban views,
        and the filters and group-bys of its search views."""
        model = model.sudo()
        target = self.env.get(model.model)
        if target is None:
            return
        existing = self.sudo().search([('model_id', '=', model.id)])
        seen = {(n.node_type, n.attr_string if n.node_type == 'page' else n.attr_name) for n in existing}
        to_create = []

        def add(node_type, key, vals):
            if key and (node_type, key) not in seen:
                seen.add((node_type, key))
                to_create.append({'model_id': model.id, 'node_type': node_type, **vals})

        views = self.env['ir.ui.view'].sudo().search([
            ('model', '=', model.model), ('type', 'in', ('form', 'list', 'kanban', 'search')), ('mode', '=', 'primary')])
        for view in views:
            try:
                arch, _view = target.sudo()._get_view(view_id=view.id, view_type=view.type)
            except Exception:
                _logger.debug("zenvio_department_login: cannot read %s view %s", model.model, view.id)
                continue
            if view.type == 'search':
                for node in arch.xpath('//filter[@name]'):
                    node_type = 'groupby' if 'group_by' in (node.get('context') or '') else 'filter'
                    add(node_type, node.get('name'), {
                        'attr_name': node.get('name'), 'attr_string': node.get('string') or node.get('name')})
                continue
            for button in arch.xpath('//button[@name][@type="object" or @type="action"]'):
                label = self._node_label(button)
                if label:
                    add('button', button.get('name'), {
                        'attr_name': button.get('name'), 'attr_string': label,
                        'is_smart': 'oe_stat_button' in (button.get('class') or ''),
                    })
            for page in arch.xpath('//page[@string]'):
                add('page', page.get('string'), {'attr_name': page.get('name'), 'attr_string': page.get('string')})
        if to_create:
            self.sudo().create(to_create)


class ZenvioAccessStateValue(models.Model):
    """Possible values of a state field, so states can be picked by label."""
    _name = 'zenvio.access.state.value'
    _description = 'Department Access Profile - State Value'
    _order = 'field_id, sequence, id'
    _rec_name = 'value_label'

    _field_value_uniq = models.Constraint(
        'UNIQUE(field_id, value_key)',
        'This state value already exists for the selected field.',
    )

    field_id = fields.Many2one('ir.model.fields', string='State Field', required=True, ondelete='cascade', index=True)
    value_key = fields.Char('Technical Value', required=True)
    value_label = fields.Char('Label')
    sequence = fields.Integer(default=10)

    @api.model
    def _sync_values(self, field):
        field = field.sudo()
        model = self.env.get(field.model_id.model)
        if model is None or field.ttype not in ('selection', 'many2one'):
            return
        existing = set(self.sudo().search([('field_id', '=', field.id)]).mapped('value_key'))
        if field.ttype == 'selection':
            selection = model.fields_get([field.name])[field.name].get('selection') or []
            values = [(str(key), label) for key, label in selection]
        else:
            values = [(str(rec.id), rec.display_name)
                      for rec in self.env[field.relation].sudo().search([], limit=1000)]
        self.sudo().create([
            {'field_id': field.id, 'value_key': key, 'value_label': label, 'sequence': seq}
            for seq, (key, label) in enumerate(values) if key not in existing
        ])
