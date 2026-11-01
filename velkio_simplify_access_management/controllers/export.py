from odoo.addons.web.controllers.export import Export
from odoo.http import request


class Export(Export):

    def get_fields(self, model, *args, **kwargs):
        # Odoo 18 replaced the ``fields_get`` controller helper with
        # ``get_fields``, which returns a *list* of field descriptors whose
        # ``id`` is the dotted export path (``prefix/field_name``). Drop the
        # entries whose field is marked invisible by an Access-Studio rule.
        result = super().get_fields(model, *args, **kwargs)
        invisible_fields = request.env['hide.field'].sudo().search([
            ('access_management_id.company_ids', 'in', request.env.company.id),
            ('model_id.model', '=', model),
            ('access_management_id.active', '=', True),
            ('access_management_id.user_ids', 'in', request.env.user.id),
            ('invisible', '=', True),
        ]).field_id.mapped('name')
        if not invisible_fields:
            return result
        hidden = set(invisible_fields) - {'id'}
        return [f for f in result if f.get('id', '').rsplit('/', 1)[-1] not in hidden]
