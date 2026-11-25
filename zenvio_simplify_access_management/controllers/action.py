import re

from odoo.addons.web.controllers.utils import ensure_db
from odoo.addons.web.controllers.action import Action
from odoo.addons.web.controllers.home import Home
from odoo.tools.translate import _
from odoo.http import request
from odoo.exceptions import UserError
from odoo import http

# Odoo 18 web-client route list (see addons/web/controllers/home.py).
WEB_CLIENT_ROUTES = ['/web', '/odoo', '/odoo/<path:subpath>', '/scoped_app/<path:subpath>']


class Action(Action):

    @http.route('/web/action/run', type='json', auth="user")
    def run(self, action_id, context=None):
        res = super().run(action_id, context)
        actions_and_prints = []
        if res and isinstance(res, dict):
            for access in request.env['remove.action'].search([
                    ('access_management_id.company_ids', 'in', request.env.company.id),
                    ('access_management_id', 'in', request.env.user.access_management_ids.ids),
                    ('model_id.model', '=', res.get('res_model'))]):
                actions_and_prints += access.mapped('report_action_ids.action_id').ids
                actions_and_prints += access.mapped('server_action_ids.action_id').ids
                for view_data in access.view_data_ids:
                    for b_view in list(res.get('views') or []):
                        if b_view[1] == view_data.techname:
                            res['views'].remove(b_view)
        return res

    @http.route('/web/action/load', type='json', auth="user", readonly=True)
    def load(self, action_id, context=None):
        res = super().load(action_id, context=context)
        if res and isinstance(res, dict):
            hidden_views = set(request.env['remove.action'].sudo().search([
                ('view_data_ids', '!=', False),
                ('access_management_id.company_ids', 'in', request.env.company.id),
                ('access_management_id', 'in', request.env.user.access_management_ids.ids),
                ('model_id.model', '=', res.get('res_model'))]).mapped('view_data_ids.techname'))
            for views_data_list in list(res.get('views') or []):
                if views_data_list[1] in hidden_views:
                    res['views'].remove(views_data_list)
            if 'views' in res and not res.get('views'):
                raise UserError(_("You don't have the permission to access any views. "
                                  "Please contact your administrator."))
        return res


class Home(Home):

    @http.route(WEB_CLIENT_ROUTES, type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        # Make sure any Access-Studio rule change is picked up on a fresh client
        # load. Only the ORM caches matter here (ACLs, ir.rule domains, menu
        # visibility, our per-user helpers) - not the asset/template caches, so
        # this is `clear_cache()`, not the heavier `clear_all_caches()` the
        # Odoo 17 build used on every request.
        request.env.registry.clear_cache()

        uid = request.session.uid
        debug = str(kw.get('debug') or '').lower()
        if uid and debug not in ('', '0', 'false'):
            # `request.env.company` is empty on this auth="none" route; resolve the
            # active company from the `cids` cookie, falling back to the user's own.
            cid = None
            cookie = request.httprequest.cookies.get('cids') or ''
            m = re.match(r'\d+', cookie.strip().strip('"').lstrip('-'))
            if m:
                cid = int(m.group(0))
            if not cid:
                cid = request.env['res.users'].sudo().browse(uid).company_id.id
            if cid and request.env['access.management'].sudo().search_count([
                    ('active', '=', True), ('company_ids', 'in', cid),
                    ('disable_debug_mode', '=', True), ('user_ids', 'in', uid)]):
                return request.redirect('/odoo?debug=0')

        return super().web_client(s_action=s_action, **kw)
