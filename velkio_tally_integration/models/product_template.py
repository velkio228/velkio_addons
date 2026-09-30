# -*- coding: utf-8 -*-
"""Outbound event hooks on product.template for syncing stock items to Tally."""
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def _outbound_allowed(record, config):
    """Whether this entity may be pushed to Tally right now.

    Normally the entity's configured direction decides. A manual "Tally Post"
    click sets ``tally_force_push`` in the context and overrides it.
    """
    if record.env.context.get("tally_force_push"):
        return True
    return config.direction in ("odoo_to_tally", "both")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("tally_no_sync"):
            for rec in records:
                rec._enqueue_tally_product()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("tally_no_sync"):
            for rec in self:
                rec._enqueue_tally_product()
        return res

    def _enqueue_tally_product(self):
        self.ensure_one()
        try:
            if not self.name:
                return
            # Services are not stock items in Tally. They reach it as ledger lines
            # on the voucher instead, so there is nothing to create as a master.
            if self.type == "service":
                return
            company = self.company_id or self.env.company
            instance = self.env["tally.instance"].search(
                [("company_id", "=", company.id), ("active", "=", True)], limit=1)
            if not instance:
                return
            cfg = instance.entity_config_ids.filtered(
                lambda c: c.entity == "stock_item" and c.enabled)
            if not cfg or not _outbound_allowed(self, cfg):
                return

            from ..services import tally_xml_builder
            identity = self.product_variant_id
            if not identity:
                return

            # Tally refuses a stock item whose group or unit it does not know yet,
            # so queue those masters ahead of this one.
            if self.categ_id:
                try:
                    self.categ_id._enqueue_tally_stock_group()
                except Exception as e:  # noqa: BLE001 - never block the product itself
                    _logger.warning("Tally stock group enqueue skipped for %s: %s", self.categ_id.id, e)
            if self.uom_id:
                try:
                    self.uom_id._enqueue_tally_uom()
                except Exception as e:  # noqa: BLE001
                    _logger.warning("Tally unit enqueue skipped for %s: %s", self.uom_id.id, e)
            # Inbound stock items map to product.product.  Keep outbound on the
            # same model so a recovered product retains one Tally GUID instead
            # of becoming a second master after the database is rebuilt.
            legacy_mapping = self.env["tally.mapping"].search([
                ("instance_id", "=", instance.id), ("entity", "=", "stock_item"),
                ("odoo_model_name", "=", self._name), ("odoo_res_id", "=", self.id),
            ], limit=1)
            if legacy_mapping and not self.env["tally.mapping"].search_count([
                    ("instance_id", "=", instance.id), ("entity", "=", "stock_item"),
                    ("odoo_model_name", "=", identity._name), ("odoo_res_id", "=", identity.id)]):
                legacy_mapping.write({
                    "odoo_model_name": identity._name, "odoo_res_id": identity.id,
                })
            mapping = self.env["tally.mapping"].search([
                ("instance_id", "=", instance.id), ("entity", "=", "stock_item"),
                ("odoo_model_name", "=", identity._name), ("odoo_res_id", "=", identity.id),
            ], limit=1)
            # Tally may reset structural fields (notably PARENT) when an
            # existing GUID is resent with ACTION="Create". Keep Create while
            # the first unsent payload is being coalesced, then use Alter for
            # records already known to either side.
            pending_create = self.env["tally.sync.queue"].search_count([
                ("instance_id", "=", instance.id), ("entity", "=", "stock_item"),
                ("odoo_model_name", "=", identity._name), ("odoo_res_id", "=", identity.id),
                ("state", "=", "pending"), ("payload", "ilike", 'ACTION="Create"'),
            ])
            action = "Create" if not mapping or pending_create else "Alter"
            guid = self.env["tally.mapping"].outbound_guid(
                instance, "stock_item", identity._name, identity.id)
            base_uom = tally_xml_builder.normalize_tally_uom(
                self.uom_id.name if self.uom_id else "Nos")
            rate_date = fields.Date.context_today(self)
            if instance.tally_educational_mode:
                rate_date = rate_date.replace(day=1)
            msg_xml = tally_xml_builder.build_stock_item_xml(
                name=self.name,
                base_uom=base_uom,
                parent_group=self.categ_id.name if self.categ_id else "Primary",
                hsn_code=getattr(self, "l10n_in_hsn_code", None),
                standard_cost=self.standard_price,
                sale_price=self.list_price,
                guid=guid,
                part_no=identity.default_code,
                barcode=identity.barcode,
                effective_date=rate_date,
                action=action,
            )
            envelope_xml = tally_xml_builder.wrap_import_envelope(
                [msg_xml], company_name=instance.tally_company)

            should_enqueue = self.env["tally.mapping"].register_outbound(
                instance=instance,
                entity="stock_item",
                model_name=identity._name,
                res_id=identity.id,
                payload_xml=envelope_xml,
                guid=guid,
                allow_tally_origin=True,
            )
            if not should_enqueue:
                return

            queue_values = {
                "instance_id": instance.id,
                "entity": "stock_item",
                "odoo_model_name": identity._name,
                "odoo_res_id": identity.id,
                "idempotency_key": "odoo_product_%s_%s" % (
                    identity.id, self.write_date and self.write_date.strftime("%Y%m%d%H%M%S") or ""),
                "payload": envelope_xml,
                "state": "pending",
            }
            # Product creation touches product.template and its automatically
            # generated product.product variant in the same transaction. Keep
            # only the newest unsent payload for that canonical variant rather
            # than producing two deliveries for one business event.
            pending = self.env["tally.sync.queue"].search([
                ("instance_id", "=", instance.id),
                ("entity", "=", "stock_item"),
                ("odoo_model_name", "=", identity._name),
                ("odoo_res_id", "=", identity.id),
                ("state", "=", "pending"),
            ], order="id desc", limit=1)
            if pending:
                pending.write({
                    "idempotency_key": queue_values["idempotency_key"],
                    "payload": envelope_xml,
                })
            else:
                self.env["tally.sync.queue"].create(queue_values)
        except Exception as e:
            _logger.warning("Tally product enqueue skipped for product %s: %s", self.id, e)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("tally_no_sync"):
            for rec in records:
                rec.product_tmpl_id._enqueue_tally_product()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("tally_no_sync"):
            for rec in self:
                rec.product_tmpl_id._enqueue_tally_product()
        return res
