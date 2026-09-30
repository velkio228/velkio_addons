# -*- coding: utf-8 -*-
"""State based access engine.

The rewrite is done in ``get_view`` (per user, *after* the shared view cache)
so two users of the same model can get different results.  We only add
``invisible`` / ``readonly`` / ``required`` **expressions** that reference the
record's state field, so the web client re-evaluates them for every record.
"""
import logging

from lxml import etree

from odoo import api, models

_logger = logging.getLogger(__name__)

_TRUE_VALUES = ('1', 'true', 'True')


def _merge_modifier(node, attr, expr):
    if expr in ('0', ''):
        return
    old = (node.get(attr) or '').strip()
    if not old:
        node.set(attr, expr)
    elif old in _TRUE_VALUES or old == expr:
        return
    elif expr == '1':
        node.set(attr, '1')
    else:
        node.set(attr, '(%s) or (%s)' % (old, expr))


class Base(models.AbstractModel):
    _inherit = 'base'

    # Per-record state expressions only make sense in views that render a
    # concrete record. Search views (and others) have no record context.
    _VELKIO_STATE_VIEW_TYPES = ('form', 'list', 'kanban')

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type not in self._VELKIO_STATE_VIEW_TYPES:
            return result
        try:
            rules = self.env['velkio.state.access']._matching_rules(self._name)
            if not rules:
                return result
            node = etree.fromstring(result['arch'])
            extra_fields = self._velkio_apply_state_access(node, rules, view_type)
            if extra_fields is None:
                return result
            result = dict(result)
            result['arch'] = etree.tostring(node, encoding='unicode')
            if extra_fields:
                models_map = {m: set(f) for m, f in result['models'].items()}
                models_map.setdefault(self._name, set()).update(extra_fields)
                result['models'] = {m: tuple(f) for m, f in models_map.items()}
        except Exception:
            _logger.exception('velkio_state_based_access: get_view rewrite failed for %s', self._name)
        return result

    @api.model
    def _velkio_apply_state_access(self, arch, rules, view_type):
        """Mutate ``arch`` in place. Return the set of state field names that
        had to be referenced (so the caller can expose them to the web client),
        or ``None`` when nothing changed."""
        changed = False
        needed_state_fields = set()

        # Only touch nodes that belong to THIS view's own model, i.e. not the
        # ones living inside a nested x2many sub-view (``<field><list>...``).
        field_nodes = (arch.xpath('.//field[not(ancestor::field)]')
                       + arch.xpath('.//label[not(ancestor::field)]'))
        button_nodes = arch.xpath('.//button[not(ancestor::field)]')
        page_nodes = arch.xpath('.//page[not(ancestor::field)]')

        for rule in rules:
            cond = rule._state_condition()
            uses_state = cond not in ('0', '1')

            # ---- fields ------------------------------------------------
            for line in rule.field_line_ids:
                names = set(line.field_ids.mapped('name'))
                if not names:
                    continue
                for fnode in field_nodes:
                    ref = fnode.get('name') if fnode.tag == 'field' else fnode.get('for')
                    if ref not in names:
                        continue
                    if line.invisible:
                        _merge_modifier(fnode, 'invisible', cond)
                        changed = True
                    if line.readonly:
                        _merge_modifier(fnode, 'readonly', cond)
                        if fnode.tag == 'field' and cond == '1':
                            fnode.set('force_save', '1')
                        changed = True
                    if line.required:
                        _merge_modifier(fnode, 'required', cond)
                        changed = True
                    if uses_state:
                        needed_state_fields.add(rule.state_field_name)

            # ---- whole form read-only -------------------------------
            if rule.readonly_form and view_type == 'form':
                for fnode in field_nodes:
                    if fnode.tag == 'field':
                        _merge_modifier(fnode, 'readonly', cond)
                changed = True
                if uses_state:
                    needed_state_fields.add(rule.state_field_name)

            # ---- tabs / pages --------------------------------------
            if rule.hide_page_ids:
                names = set(rule.hide_page_ids.filtered('attr_name').mapped('attr_name'))
                strings = set(rule.hide_page_ids.mapped('attr_string'))
                for pnode in page_nodes:
                    if pnode.get('name') in names or pnode.get('string') in strings:
                        _merge_modifier(pnode, 'invisible', cond)
                        changed = True
                        if uses_state:
                            needed_state_fields.add(rule.state_field_name)

            # ---- buttons ------------------------------------------
            if rule.hide_button_ids:
                names = set(rule.hide_button_ids.filtered('attr_name').mapped('attr_name'))
                for bnode in button_nodes:
                    if bnode.get('name') in names:
                        _merge_modifier(bnode, 'invisible', cond)
                        changed = True
                        if uses_state:
                            needed_state_fields.add(rule.state_field_name)

            # ---- chatter (not state dependent) ------------------
            if rule.hide_chatter and view_type == 'form':
                for chatter in arch.xpath('.//chatter') + arch.xpath(".//div[@class='oe_chatter']"):
                    parent = chatter.getparent()
                    if parent is not None:
                        parent.remove(chatter)
                        changed = True

        if not changed:
            return None

        # Make sure every referenced state field is really loaded by the web
        # client: it must be present as a top-level <field> node of this view
        # (a node inside a sub-view, or one removed by group access rights,
        # does not count). Otherwise inject a hidden one.
        for fname in needed_state_fields:
            if not fname:
                continue
            existing = arch.xpath(".//field[@name='%s'][not(ancestor::field)]" % fname)
            if view_type != 'list':
                existing = [n for n in existing
                            if (n.get('column_invisible') or '').lower() not in ('1', 'true')]
            if existing:
                continue
            el = etree.Element('field', {'name': fname})
            if view_type == 'list':
                el.set('column_invisible', '1')
            else:
                el.set('invisible', '1')
            sheet = arch.find('.//sheet')
            if sheet is not None:
                sheet.insert(0, el)
            else:
                arch.append(el)

        return needed_state_fields
