# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class VelkioStateAccessNode(models.Model):
    """Cache of the tabs / buttons found in a model's views so the user can
    pick them from a list instead of typing technical names."""

    _name = 'velkio.state.access.node'
    _description = 'State Based Access - View Node'
    _order = 'node_type, attr_string, id'
    _rec_name = 'display_label'

    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade', index=True)
    model_name = fields.Char(related='model_id.model', store=True, string='Model Technical Name')
    node_type = fields.Selection(
        [('page', 'Tab / Page'), ('button', 'Button')],
        string='Type', required=True)
    attr_name = fields.Char('Technical Name')
    attr_string = fields.Char('Label', required=True)
    button_type = fields.Char('Button Type')
    is_smart = fields.Boolean('Smart Button')
    display_label = fields.Char(compute='_compute_display_label', store=True)

    @api.depends('attr_string', 'attr_name', 'is_smart')
    def _compute_display_label(self):
        for rec in self:
            name = rec.attr_string or ''
            if rec.attr_name:
                name += ' (%s)' % rec.attr_name
            if rec.is_smart:
                name += ' [Smart]'
            rec.display_label = name

    @api.model
    def _node_label(self, node):
        label = node.get('string') or ''
        if not label:
            texts = [t.strip() for t in node.xpath('.//text()') if t and t.strip()]
            label = ' '.join(texts)
        return label.strip()[:120]

    @api.model
    def _sync_nodes(self, model):
        """Populate the tab / button cache for ``model`` from its views."""
        model = model.sudo()
        target = self.env.get(model.model)
        if target is None:
            return
        View = self.env['ir.ui.view'].sudo()
        existing = self.search([('model_id', '=', model.id)])
        seen_pages = set(existing.filtered(lambda n: n.node_type == 'page').mapped('attr_string'))
        seen_btns = set(existing.filtered(lambda n: n.node_type == 'button').mapped('attr_name'))
        to_create = []
        for view_type in ('form', 'list', 'kanban'):
            for view in View.search([('model', '=', model.model), ('type', '=', view_type)]):
                try:
                    arch, _view = target._get_view(view_id=view.id, view_type=view_type)
                except Exception:
                    _logger.debug('velkio_state_based_access: cannot read %s view of %s',
                                  view_type, model.model)
                    continue
                for btn in arch.xpath('//button[@name]'):
                    name = btn.get('name')
                    label = self._node_label(btn)
                    if not name or not label or name in seen_btns:
                        continue
                    seen_btns.add(name)
                    to_create.append({
                        'model_id': model.id, 'node_type': 'button',
                        'attr_name': name, 'attr_string': label,
                        'button_type': btn.get('type'),
                        'is_smart': 'oe_stat_button' in (btn.get('class') or ''),
                    })
                for page in arch.xpath('//page[@string]'):
                    label = page.get('string')
                    if not label or label in seen_pages:
                        continue
                    seen_pages.add(label)
                    to_create.append({
                        'model_id': model.id, 'node_type': 'page',
                        'attr_name': page.get('name'), 'attr_string': label,
                    })
        if to_create:
            self.create(to_create)
