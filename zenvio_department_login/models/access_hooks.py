"""Apply the access profile of the employee working in the current session.

Employees log in as their Top Management user, so Odoo's own caches (keyed by
user id) cannot tell them apart. Every hook here either runs after those
caches or adds the session's employee to their key, and only ever takes
rights away.
"""
import ast

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

# Models an employee never touches: the department login setup itself.
PROTECTED_MODELS = frozenset({
    'zenvio.department.access', 'zenvio.department.employee', 'zenvio.department.login.log',
    'zenvio.access.profile', 'zenvio.access.profile.model', 'zenvio.access.profile.field',
    'zenvio.access.profile.domain', 'zenvio.access.profile.button', 'zenvio.access.profile.filter',
    'zenvio.access.profile.chatter', 'zenvio.access.view.node', 'zenvio.access.state.value',
    'zenvio.department.move',
})
# Security and system setup an employee may read but never change, even when
# the Top Management user is an administrator: rights, users' access, modules, settings, code.
SYSTEM_MODELS = frozenset({
    'res.groups', 'res.groups.privilege', 'ir.model.access', 'ir.rule', 'ir.module.module',
    'ir.module.category', 'ir.config_parameter', 'ir.model', 'ir.model.fields', 'ir.model.fields.selection',
    'ir.model.constraint', 'ir.model.relation', 'ir.model.data', 'ir.ui.menu', 'ir.ui.view',
    'ir.actions.actions', 'ir.actions.act_window', 'ir.actions.act_window.view', 'ir.actions.server',
    'ir.actions.client', 'ir.actions.report', 'ir.actions.act_url', 'ir.cron', 'ir.mail_server',
    'base.automation', 'res.users.apikeys', 'auth.passkey.key', 'res.company', 'ir.filters.server',
    'res.users.identitycheck', 'change.password.wizard', 'change.password.user', 'res.users.apikeys.description',
    'base.module.upgrade', 'base.module.uninstall', 'base.language.install', 'res.config.settings',
    'auth_totp.wizard', 'res.users.apikeys.show', 'change.password.own', 'res.users.deletion',
})
# Models a read-only employee may still write: chatter, notifications, own settings.
READONLY_EXEMPT_PREFIXES = ('mail.', 'bus.', 'discuss.', 'res.users.settings', 'res.users.log', 'res.device',
                            'ir.attachment')
VIEW_TYPES = ('form', 'list', 'kanban')
RELATIONAL = ('many2one', 'many2many')
NO_LINK_OPTIONS = {'no_create': True, 'no_create_edit': True, 'no_quick_create': True, 'no_open': True}
# Chatter switch -> class put on the form, hiding that chatter button (department_login.scss).
CHATTER_CLASSES = {
    'hide_send_message': 'o_zenvio_no_send_message',
    'hide_log_note': 'o_zenvio_no_log_note',
    'hide_activity': 'o_zenvio_no_activity',
}


def _merge_modifier(node, attr, expr):
    old = (node.get(attr) or '').strip()
    if not old or expr == '1':
        node.set(attr, expr)
    elif old not in ('1', 'True', 'true') and old != expr:
        node.set(attr, '(%s) or (%s)' % (old, expr))


def _merged(conds):
    return '1' if '1' in conds else ' or '.join('(%s)' % c for c in conds)


def _session(env):
    return env['zenvio.department.employee']._zenvio_session()


def _flag(session, model, flag):
    """A switch of the profile: on everywhere (Global tab) or for this model."""
    rules = session['rules']
    rule = rules['models'].get(model)
    return bool(rules.get(flag) or (rule and rule.get(flag)))


def _denies(session, model, mode):
    if model in PROTECTED_MODELS or (mode != 'read' and model in SYSTEM_MODELS):
        return True
    if model == 'res.users' and mode in ('create', 'unlink'):
        return True  # no new accounts (with any groups) and no deleting accounts
    if model == 'mail.activity' and mode == 'create' and session['rules']['hide_activity']:
        return True
    rules = session['rules']
    rule = rules['models'].get(model)
    if rule and mode in rule['denied']:
        return True
    return bool(rules['readonly'] and mode != 'read' and not model.startswith(READONLY_EXEMPT_PREFIXES))


def _set_options(node, extra):
    """Merge ``extra`` into a field's options; leave options we cannot parse."""
    text = (node.get('options') or '').strip()
    try:
        options = ast.literal_eval(text) if text else {}
    except (ValueError, SyntaxError):
        return
    if isinstance(options, dict):
        node.set('options', repr({**options, **extra}))


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        has_access = super().check(model, mode, raise_exception)
        if has_access and not self.env.su:
            session = _session(self.env)
            if session and _denies(session, model, mode) and (
                    model in SYSTEM_MODELS or model in PROTECTED_MODELS
                    or not (model in self.env and self.env[model]._transient)):
                if raise_exception:
                    raise self._make_access_error(model, mode)
                return False
        return has_access


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain_context_values(self):
        # Keep the cached record rules of each employee apart from the Top Management user's own.
        yield from super()._compute_domain_context_values()
        session = _session(self.env)
        yield session and session['line_id']

    @api.model
    def _compute_domain(self, model_name, mode='read'):
        domain = super()._compute_domain(model_name, mode)
        session = _session(self.env)
        rule = session and session['rules']['models'].get(model_name)
        if not rule or not rule['domains']:
            return domain
        eval_context = dict(
            self._eval_context(),
            employee=self.env['hr.employee'].sudo().browse(session['employee_id']),
            department=self.env['hr.department'].sudo().browse(session['department_id']),
        )
        extra = [Domain(safe_eval(text, eval_context)) for text in rule['domains']]
        return Domain.AND([domain, *extra]).optimize(self.env[model_name])


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def load_menus(self, debug):
        menus = super().load_menus(debug)
        session = _session(self.env)
        if not session:
            return menus
        own_root = self.env.ref('zenvio_department_login.menu_zenvio_department_root', raise_if_not_found=False)
        hidden = set(session['rules']['hidden_menu_ids'])
        if own_root:
            hidden |= set(self.sudo().search([('id', 'child_of', own_root.id)]).ids)
        # The result is cached and shared with the Top Management user: build a filtered copy.
        return {
            key: dict(menu, children=[child for child in menu['children'] if child not in hidden])
            for key, menu in menus.items() if key not in hidden
        }


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        result = super().get_views(views, options)
        session = _session(self.env)
        if not session:
            return result
        # Print / Actions menus of this model.
        for key, flag in (('print', 'hide_print'), ('action', 'hide_actions')):
            if _flag(session, self._name, flag):
                for view in result['views'].values():
                    if view.get('toolbar'):
                        view['toolbar'] = dict(view['toolbar'], **{key: []})
        # Archive / Unarchive is only offered when 'active' is editable.
        if _flag(session, self._name, 'hide_archive'):
            fields_info = result['models'].get(self._name, {}).get('fields', {})
            for name in ('active', 'x_active'):
                if name in fields_info:
                    fields_info[name] = dict(fields_info[name], readonly=True)
        return result

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type not in VIEW_TYPES + ('search',):
            return result
        session = _session(self.env)
        if not session:
            return result
        rules = session['rules']
        rule = rules['models'].get(self._name) or {}
        arch = etree.fromstring(result['arch'])
        if view_type == 'search':
            changed = self._zenvio_apply_search(arch, rule)
            needed_fields = set()
        else:
            changed = True
            needed_fields = self._zenvio_apply_profile(arch, view_type, rule, rules)
        if not changed:
            return result
        result = dict(result, arch=etree.tostring(arch, encoding='unicode'))
        if needed_fields:
            models_map = {model: set(names) for model, names in result['models'].items()}
            models_map.setdefault(self._name, set()).update(needed_fields)
            result['models'] = {model: tuple(names) for model, names in models_map.items()}
        return result

    @api.model
    def _zenvio_apply_search(self, arch, rule):
        hidden = rule.get('filters')
        if not hidden:
            return False
        for node in arch.xpath('.//filter[@name]'):
            if node.get('name') in hidden:
                node.set('invisible', '1')
        return True

    @api.model
    def _zenvio_apply_profile(self, arch, view_type, rule, rules):
        """Hide / lock the nodes of this view's own model (not of sub-views).
        Return the state fields the new expressions need loaded."""
        denied = rule.get('denied', ())
        readonly = rules['readonly'] or {'write', 'create', 'unlink'} <= set(denied)
        for mode, attr in (('create', 'create'), ('write', 'edit'), ('unlink', 'delete')):
            if readonly or mode in denied:
                arch.set(attr, '0')
        if view_type == 'form' and (rule.get('hide_duplicate') or readonly):
            arch.set('duplicate', '0')
        if view_type in ('list', 'kanban') and (rule.get('hide_import') or rules['hide_import'] or readonly):
            arch.set('import', '0')
        if view_type == 'list' and (rule.get('hide_export') or rules['hide_export']):
            arch.set('export_xlsx', '0')

        fields_info = self._fields
        field_nodes = arch.xpath('.//field[not(ancestor::field)]')
        label_nodes = arch.xpath('.//label[@for][not(ancestor::field)]')
        for node in field_nodes + label_nodes:
            name = node.get('name') if node.tag == 'field' else node.get('for')
            if conds := rule.get('invisible', {}).get(name):
                if view_type == 'list' and node.getparent() is arch and '1' in conds:
                    _merge_modifier(node, 'column_invisible', '1')
                else:
                    _merge_modifier(node, 'invisible', _merged(conds))
            if node.tag != 'field':
                continue
            field = fields_info.get(name)
            if readonly:
                _merge_modifier(node, 'readonly', '1')
            elif conds := rule.get('readonly_fields', {}).get(name):
                _merge_modifier(node, 'readonly', _merged(conds))
                node.set('force_save', '1')
            if conds := rule.get('required_fields', {}).get(name):
                _merge_modifier(node, 'required', _merged(conds))
            if field is not None and field.type in RELATIONAL and (
                    rules['disable_relational_edit'] or name in rule.get('no_open_fields', ())):
                _set_options(node, NO_LINK_OPTIONS)
            if field is not None and field.type == 'properties' and rules['hide_add_property']:
                _merge_modifier(node, 'readonly', '1')

        for node in arch.xpath('.//button[@name][not(ancestor::field)]'):
            if entries := rule.get('buttons', {}).get(node.get('name')):
                conds = ['%s in %r' % (field, list(values)) if values else '1' for field, values in entries]
                _merge_modifier(node, 'invisible', _merged(conds))

        pages = rule.get('pages', {})
        for node in arch.xpath('.//page[not(ancestor::field)]'):
            conds = [cond for (name, label), cond_list in pages.items()
                     if (name and node.get('name') == name) or node.get('string') == label
                     for cond in cond_list]
            if conds:
                _merge_modifier(node, 'invisible', _merged(conds))

        if view_type == 'form':
            if rule.get('hide_chatter') or rules['hide_chatter']:
                for node in arch.xpath('.//chatter') + arch.xpath(".//div[contains(concat(' ', @class, ' '), ' oe_chatter ')]"):
                    node.getparent().remove(node)
            classes = [css for flag, css in CHATTER_CLASSES.items() if rule.get(flag) or rules[flag]]
            if classes:
                arch.set('class', ' '.join(filter(None, [arch.get('class'), *classes])))

        # Expressions on a state field only work if the field is loaded.
        needed = set(rule.get('state_fields', ()))
        for name in needed:
            if arch.xpath(".//field[@name='%s'][not(ancestor::field)]" % name):
                continue
            node = etree.Element('field', {'name': name})
            node.set('column_invisible' if view_type == 'list' else 'invisible', '1')
            (arch.find('.//sheet') if arch.find('.//sheet') is not None else arch).insert(0, node)
        return needed

    @api.model
    def _zenvio_check_button(self, method, ids):
        """Refuse a hidden button called through RPC (in the states it is hidden)."""
        session = _session(self.env)
        rule = session and session['rules']['models'].get(self._name)
        entries = rule and rule['buttons'].get(method)
        if not entries:
            return
        records = self.sudo().browse(ids).exists()
        for field, values in entries:
            if not values or any(
                (record[field].id if record._fields[field].type == 'many2one' else record[field]) in values
                for record in records
            ):
                raise AccessError(_("You are not allowed to use this button."))

    def export_data(self, fields_to_export):
        session = _session(self.env)
        if session and _flag(session, self._name, 'hide_export'):
            raise AccessError(_("You are not allowed to export these records."))
        return super().export_data(fields_to_export)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_post(self, **kwargs):
        session = _session(self.env)
        if session:
            subtype = kwargs.get('subtype_xmlid') or ''
            is_note = subtype == 'mail.mt_note' or (
                kwargs.get('subtype_id') and kwargs['subtype_id'] == self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'))
            if kwargs.get('message_type', 'notification') == 'comment':
                flag = 'hide_log_note' if is_note else 'hide_send_message'
                if _flag(session, self._name, flag):
                    raise AccessError(_("You are not allowed to post here."))
        return super().message_post(**kwargs)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        session = _session(self.env)
        if session:
            for vals in vals_list:
                model = vals.get('res_model') or self.env['ir.model'].sudo().browse(vals.get('res_model_id')).model
                if model and _flag(session, model, 'hide_activity'):
                    raise AccessError(_("You are not allowed to schedule activities here."))
        return super().create(vals_list)
