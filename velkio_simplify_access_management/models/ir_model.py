# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _


class IrModel(models.Model):
    _inherit = 'ir.model'

    # Odoo 18 exposes ``_abstract`` only as a Python attribute, not as a stored
    # field on ``ir.model``. Access Studio needs it in view domains
    # (``[('abstract', '=', False)]``), so keep our own copy, filled on
    # install/upgrade by ``ir.module.module._button_immediate_function`` below.
    abstract = fields.Boolean('Abstract', readonly=True)

    @api.depends_context('is_access_rights')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('is_access_rights'):
            for model in self:
                model.display_name = "{} ({})".format(model.name, model.model)


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.depends_context('is_access_rights')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('is_access_rights'):
            for field in self:
                field.display_name = "{} => {} ({})".format(
                    field.field_description, field.name, field.model_id.model)


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _button_immediate_function(self, function):
        res = super()._button_immediate_function(function)
        if function.__name__ in ['button_install', 'button_upgrade']:
            for record in self.env['ir.model'].search([]):
                if record.model in self.env.registry:
                    record.abstract = self.env[record.model]._abstract
                else:
                    record.abstract = False
        return res
