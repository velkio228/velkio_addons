# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VelkioStateAccess(models.Model):
    _name = 'velkio.state.access'
    _description = 'State Based Access Rule'
    _order = 'sequence, id'

    name = fields.Char('Rule Name', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    note = fields.Text('Notes')

    company_ids = fields.Many2many(
        'res.company', 'velkio_state_access_company_rel', 'rule_id', 'company_id',
        string='Companies', required=True,
        default=lambda self: self.env.company)

    user_ids = fields.Many2many(
        'res.users', 'velkio_state_access_users_rel', 'rule_id', 'user_id',
        string='Users', domain="[('share', '=', False)]")
    group_ids = fields.Many2many(
        'res.groups', 'velkio_state_access_groups_rel', 'rule_id', 'group_id',
        string='Groups')
    apply_to_all = fields.Boolean(
        string='Apply to Everyone', compute='_compute_apply_to_all', store=True,
        help='Set automatically when no user and no group is selected.')

    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(related='model_id.model', store=True, string='Model Technical Name')

    state_field_id = fields.Many2one(
        'ir.model.fields', string='State Field', required=True, ondelete='cascade',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['selection', 'many2one'])]")
    state_field_name = fields.Char(related='state_field_id.name', store=True)
    state_field_ttype = fields.Selection(related='state_field_id.ttype', store=True)

    value_ids = fields.Many2many(
        'velkio.state.access.value', 'velkio_state_access_value_rel',
        'rule_id', 'value_id', string='Applies in States',
        help='The rule is enforced only when the record state is one of these '
             'values. Leave empty to enforce it in every state.')

    field_line_ids = fields.One2many(
        'velkio.state.access.field.line', 'rule_id', string='Field Restrictions',
        copy=True)
    hide_page_ids = fields.Many2many(
        'velkio.state.access.node', 'velkio_state_access_page_rel',
        'rule_id', 'node_id', string='Hide Tabs / Pages',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'page')]")
    hide_button_ids = fields.Many2many(
        'velkio.state.access.node', 'velkio_state_access_button_rel',
        'rule_id', 'node_id', string='Hide Buttons',
        domain="[('model_id', '=', model_id), ('node_type', '=', 'button')]")

    readonly_form = fields.Boolean(
        string='Whole Form Read-Only',
        help='In the selected states, every field of the form view becomes read-only.')
    hide_chatter = fields.Boolean(
        string='Hide Chatter',
        help='Remove the chatter (messages / log notes / activities) from the '
             'form view. Not state dependent.')

    rule_count = fields.Integer(compute='_compute_rule_count', string='Restrictions')

    # ------------------------------------------------------------------
    # Compute / constraints
    # ------------------------------------------------------------------
    @api.depends('user_ids', 'group_ids')
    def _compute_apply_to_all(self):
        for rec in self:
            rec.apply_to_all = not rec.user_ids and not rec.group_ids

    @api.depends('field_line_ids', 'hide_page_ids', 'hide_button_ids',
                 'readonly_form', 'hide_chatter')
    def _compute_rule_count(self):
        for rec in self:
            rec.rule_count = (
                len(rec.field_line_ids) + len(rec.hide_page_ids)
                + len(rec.hide_button_ids)
                + (1 if rec.readonly_form else 0)
                + (1 if rec.hide_chatter else 0)
            )

    @api.constrains('state_field_id', 'model_id')
    def _check_state_field(self):
        for rec in self:
            if rec.state_field_id.model_id != rec.model_id:
                raise ValidationError(_('The state field must belong to the selected model.'))

    # ------------------------------------------------------------------
    # Onchange - keep the helper caches fresh
    # ------------------------------------------------------------------
    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.state_field_id = False
        self.value_ids = [(5, 0, 0)]
        self.field_line_ids = [(5, 0, 0)]
        self.hide_page_ids = [(5, 0, 0)]
        self.hide_button_ids = [(5, 0, 0)]
        if self.model_id:
            self.env['velkio.state.access.node']._sync_nodes(self.model_id)
            default_state = self.env['ir.model.fields'].search([
                ('model_id', '=', self.model_id.id),
                ('name', '=', 'state'), ('ttype', '=', 'selection')], limit=1)
            if default_state:
                self.state_field_id = default_state.id

    @api.onchange('state_field_id')
    def _onchange_state_field_id(self):
        self.value_ids = [(5, 0, 0)]
        if self.state_field_id:
            self.env['velkio.state.access.value']._sync_values(self.state_field_id)

    # ------------------------------------------------------------------
    # CRUD - refresh helper caches and drop the view cache
    # ------------------------------------------------------------------
    def _refresh_caches(self):
        for rec in self:
            if rec.state_field_id:
                self.env['velkio.state.access.value']._sync_values(rec.state_field_id)
            if rec.model_id:
                self.env['velkio.state.access.node']._sync_nodes(rec.model_id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._refresh_caches()
        return res

    def action_sync_helpers(self):
        self._refresh_caches()
        return True

    # ------------------------------------------------------------------
    # Engine helpers (called from ir.ui.view)
    # ------------------------------------------------------------------
    @api.model
    def _matching_rules(self, model_name):
        """Active rules for ``model_name`` that match the current user/company."""
        user = self.env.user
        rules = self.sudo().search([
            ('active', '=', True),
            ('model_name', '=', model_name),
            ('company_ids', 'in', self.env.company.ids),
        ])
        if not rules:
            return rules
        user_groups = user.all_group_ids
        matched = self.browse()
        for rule in rules:
            if rule.apply_to_all:
                matched |= rule
            elif user in rule.user_ids:
                matched |= rule
            elif rule.group_ids & user_groups:
                matched |= rule
        return matched

    def _state_condition(self):
        """Python expression (string) that is truthy when the record is in one
        of the rule's target states. ``'1'`` means "always"."""
        self.ensure_one()
        field = self.state_field_name
        if not field:
            return '0'
        if not self.value_ids:
            return '1'
        if self.state_field_ttype == 'many2one':
            keys = [int(v.value_key) for v in self.value_ids
                    if (v.value_key or '').isdigit()]
            return '%s in %s' % (field, keys or [0])
        keys = [v.value_key for v in self.value_ids]
        return '%s in %s' % (field, keys)


class VelkioStateAccessFieldLine(models.Model):
    _name = 'velkio.state.access.field.line'
    _description = 'State Based Access - Field Restriction'

    rule_id = fields.Many2one('velkio.state.access', required=True, ondelete='cascade')
    model_id = fields.Many2one(related='rule_id.model_id', store=True)
    field_ids = fields.Many2many(
        'ir.model.fields', 'velkio_state_access_field_line_rel',
        'line_id', 'field_id', string='Fields', required=True,
        domain="[('model_id', '=', model_id)]")
    invisible = fields.Boolean(default=True)
    readonly = fields.Boolean()
    required = fields.Boolean()

    @api.constrains('invisible', 'readonly', 'required')
    def _check_something_selected(self):
        for rec in self:
            if not (rec.invisible or rec.readonly or rec.required):
                raise ValidationError(
                    _('Pick at least one of Invisible / Read-Only / Required.'))
