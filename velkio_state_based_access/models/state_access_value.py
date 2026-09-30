# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class VelkioStateAccessValue(models.Model):
    """Cache of the possible values of a state field, used to let the user
    pick, from a nice list, the states a rule should apply to."""

    _name = 'velkio.state.access.value'
    _description = 'State Based Access - State Value'
    _order = 'field_id, sequence, id'
    _rec_name = 'display_label'

    field_id = fields.Many2one(
        'ir.model.fields', string='State Field', required=True,
        ondelete='cascade', index=True)
    model_name = fields.Char(related='field_id.model_id.model', store=True,
                             string='Model Technical Name')
    field_name = fields.Char(related='field_id.name', store=True,
                             string='Field Technical Name')
    value_key = fields.Char('Technical Value', required=True)
    value_label = fields.Char('Label')
    sequence = fields.Integer(default=10)
    display_label = fields.Char(compute='_compute_display_label', store=True)

    _sql_constraints = [
        ('uniq_field_value', 'unique(field_id, value_key)',
         'This state value already exists for the selected field.'),
    ]

    @api.depends('value_label', 'value_key')
    def _compute_display_label(self):
        for rec in self:
            label = rec.value_label or rec.value_key or ''
            rec.display_label = '%s (%s)' % (label, rec.value_key or '')

    @api.model
    def _sync_values(self, field):
        """Make sure the value cache is populated for ``field``."""
        field = field.sudo()
        if not field or field.ttype not in ('selection', 'many2one'):
            return
        model = self.env.get(field.model_id.model)
        if model is None:
            return
        existing = set(self.search([('field_id', '=', field.id)]).mapped('value_key'))
        to_create = []
        seq = 10
        if field.ttype == 'selection':
            try:
                selection = model.fields_get([field.name])[field.name].get('selection') or []
            except Exception:
                _logger.warning('velkio_state_based_access: cannot read selection of %s.%s',
                                field.model_id.model, field.name)
                selection = []
            for key, label in selection:
                if str(key) not in existing:
                    to_create.append({
                        'field_id': field.id, 'value_key': str(key),
                        'value_label': label, 'sequence': seq,
                    })
                seq += 10
        else:  # many2one -> list the related records (capped)
            comodel = field.relation
            if comodel and self.env.get(comodel) is not None:
                for rec in self.env[comodel].sudo().search([], limit=1000):
                    if str(rec.id) not in existing:
                        to_create.append({
                            'field_id': field.id, 'value_key': str(rec.id),
                            'value_label': rec.display_name, 'sequence': seq,
                        })
                    seq += 10
        if to_create:
            self.create(to_create)
