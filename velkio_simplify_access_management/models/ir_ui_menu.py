from odoo import models, api
from odoo.http import request


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _velkio_hidden_menu_ids(self):
        """ Menu ids the current user must not see, for the current company. """
        cid = self.env.company.id
        if request and request.httprequest.cookies.get('cids'):
            import re
            m = re.match(r'\d+', request.httprequest.cookies.get('cids').strip().strip('"').lstrip('-'))
            if m:
                cid = int(m.group(0))
        packs = self.env.user.access_management_ids.filtered(
            lambda a: a.active and cid in a.company_ids.ids)
        return set(packs.mapped('hide_menu_ids.menu_id'))

    def _filter_visible_menus(self):
        """ Odoo 18 builds the web-client menu tree through
        ``search_fetch(...)._filter_visible_menus()`` (not ``search``), so the
        menu-hiding rule is applied here. ``load_menus`` is ormcache'd per uid,
        so per-user filtering is safe. """
        menus = super()._filter_visible_menus()
        hidden = self._velkio_hidden_menu_ids()
        if hidden:
            menus = menus.filtered(lambda m: m.id not in hidden)
        return menus

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        ids = super().search(domain, offset=0, limit=None, order=order)
        hidden = self._velkio_hidden_menu_ids()
        if hidden:
            ids = ids.filtered(lambda m: m.id not in hidden)
        if offset:
            ids = ids[offset:]
        if limit:
            ids = ids[:limit]
        return ids

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        menu_item_obj = self.env['menu.item']
        for record in res:
            menu_item_obj.create({'name': record.display_name, 'menu_id': record.id})
        return res

    def unlink(self):
        menu_item_obj = self.env['menu.item']
        for record in self:
            menu_item_obj.search([('menu_id', '=', record.id)]).unlink()
        return super().unlink()
