# -*- coding: utf-8 -*-
import logging
from odoo import api, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Models every internal user must be able to READ for Access Studio to work:
# the module traverses ``model_id.model`` in domains all over the code base
# (``_get_view``, ``hide.view.nodes``, controllers, exports...), which Odoo 18
# otherwise blocks for non-admins. This mirrors the Odoo 17 build.
_ALWAYS_READABLE = ('ir.model', 'ir.model.fields', 'mail.thread')


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    def _velkio_bypass_active(self):
        """ True while the module is being uninstalled - all dynamic ACL logic
        must be skipped then (its tables are about to be dropped). """
        return bool(self.env['ir.config_parameter'].sudo().get_param(
            'uninstall_velkio_simplify_access_management'))

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        # Odoo 18 rewrote ``check`` to delegate to the ormcache'd
        # ``_get_allowed_models``. We keep the standard behaviour via ``super``
        # and layer the Access-Studio rules on top.
        reg = self.env.registry
        if (self.env.su or not isinstance(model, str)
                or not reg.ready or reg._init):
            # never run the dynamic logic while modules are (un)loading: the
            # extra ORM search would flush half-built records and slow the
            # install/upgrade to a crawl.
            return super().check(model, mode, raise_exception=raise_exception)

        if mode == 'read' and model in _ALWAYS_READABLE:
            return True

        access_mgmt = self.env['access.management'].sudo()
        try:
            domain_models = access_mgmt._domain_ah_models()
            readonly = access_mgmt._has_readonly_restriction()
        except Exception:  # noqa: BLE001 - never let Access Studio break base ACLs
            domain_models, readonly = frozenset(), False

        # Only pay for the extra work (and the uninstall-guard lookup) when the
        # current user actually has an Access-Studio rule in play.
        if (domain_models or readonly) and self._velkio_bypass_active():
            return super().check(model, mode, raise_exception=raise_exception)

        # 1. an active "Domain Access" rule grants base model access; the real
        #    record filtering is enforced by ``ir.rule._compute_domain``.
        if model in domain_models:
            return True

        res = super().check(model, mode, raise_exception=raise_exception)

        # 2. a read-only user is denied every non-read operation.
        if res and readonly and mode != 'read':
            if raise_exception:
                raise AccessError(
                    _('%s is a read-only user, so no changes can be made in the system!',
                      self.env.user.name))
            return False

        return res
