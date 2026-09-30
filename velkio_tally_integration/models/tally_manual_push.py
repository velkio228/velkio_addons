# -*- coding: utf-8 -*-
"""Manual "Tally Post" buttons.

Records normally reach Tally through the event hooks (posting an invoice, saving
a master) and the queue is dispatched by the direct-sync cron. These buttons let
a user push one record on demand and see the result straight away, which is what
the document forms expose.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TallyManualPushMixin(models.AbstractModel):
    """Shared implementation for every model that owns a Tally Post button."""

    _name = "tally.manual.push.mixin"
    _description = "Tally Manual Push"

    # Name of the enqueue hook the concrete model already implements.
    _tally_enqueue_method = None

    tally_sync_state = fields.Selection(
        [("none", "Not sent to Tally"), ("queued", "Waiting to be posted"),
         ("failed", "Failed"), ("posted", "In Tally"), ("from_tally", "Came from Tally")],
        string="Tally Status", compute="_compute_tally_sync_state",
        help="Where this record stands with Tally right now.")
    tally_last_sync = fields.Datetime(
        string="Last Tally Sync", compute="_compute_tally_sync_state")

    @api.depends_context("company")
    def _compute_tally_sync_state(self):
        Queue = self.env["tally.sync.queue"].sudo()
        Mapping = self.env["tally.mapping"].sudo()
        for record in self:
            record.tally_sync_state = "none"
            record.tally_last_sync = False
            if not record.id:
                continue
            domain = [("odoo_model_name", "=", record._name), ("odoo_res_id", "=", record.id)]
            queued = Queue.search(domain + [("state", "in", ("pending", "sent", "failed"))],
                                  order="create_date desc", limit=1)
            if queued:
                record.tally_sync_state = "failed" if queued.state == "failed" else "queued"
                continue
            mapping = Mapping.search(domain, limit=1)
            if mapping:
                record.tally_sync_state = "from_tally" if mapping.last_origin == "tally" else "posted"
                record.tally_last_sync = mapping.last_sync

    def _tally_push_instances(self):
        """Active instances for the companies of these records."""
        companies = self.env["res.company"]
        for record in self:
            company = (getattr(record, "company_id", False)
                       or (getattr(record, "company_ids", False) and record.company_ids[:1])
                       or self.env.company)
            companies |= company
        return self.env["tally.instance"].search([
            ("company_id", "in", companies.ids), ("active", "=", True),
        ])

    def action_tally_post(self):
        """Queue these records for Tally and dispatch the queue immediately."""
        if not self:
            return False
        instances = self._tally_push_instances()
        if not instances:
            raise UserError(_("No active Tally instance is configured for this company."))

        Queue = self.env["tally.sync.queue"]
        before = Queue.search_count([("instance_id", "in", instances.ids)])
        records = self.with_context(tally_force_push=True)
        for record in records:
            getattr(record, record._tally_enqueue_method)()
        queued = Queue.search_count([("instance_id", "in", instances.ids)]) - before

        if not queued:
            return self._tally_notification(
                _("Nothing to post"),
                _("Tally already holds the current version of this record."),
                "warning")

        errors = []
        for instance in instances:
            try:
                instance._direct_dispatch_queue()
            except Exception as e:                      # noqa: BLE001 - surfaced to the user
                _logger.warning("Manual Tally push failed for instance %s: %s", instance.id, e)
                errors.append("%s: %s" % (instance.name, e))

        pending = Queue.search_count([
            ("instance_id", "in", instances.ids), ("state", "in", ("pending", "failed")),
        ])
        if errors:
            return self._tally_notification(
                _("Queued, but not delivered"),
                _("%(count)s item(s) queued. Tally could not be reached — they stay in the "
                  "queue and the sync job will retry.\n%(errors)s",
                  count=queued, errors="\n".join(errors)),
                "warning")
        if pending:
            return self._tally_notification(
                _("Queued for Tally"),
                _("%(count)s item(s) queued; %(pending)s still waiting. Check "
                  "Tally → Operations → Sync Queue.", count=queued, pending=pending),
                "warning")
        return self._tally_notification(
            _("Posted to Tally"),
            _("%s item(s) posted to Tally, including any masters they depend on.") % queued,
            "success")

    def _tally_notification(self, title, message, level):
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": title, "message": message, "type": level, "sticky": False},
        }


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_voucher"

    def action_tally_post(self):
        unposted = self.filtered(lambda m: m.state != "posted")
        if unposted:
            raise UserError(_("Post the document in Odoo before posting it to Tally: %s")
                            % ", ".join(unposted.mapped("name")))
        return super().action_tally_post()


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_payment"

    def action_tally_post(self):
        draft = self.filtered(lambda p: p.state == "draft")
        if draft:
            raise UserError(_("Confirm the payment before posting it to Tally: %s")
                            % ", ".join(draft.mapped("name")))
        return super().action_tally_post()


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_stock_journal"


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_party"


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_product"


class AccountAccount(models.Model):
    _name = "account.account"
    _inherit = ["account.account", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_account"


class AccountTax(models.Model):
    _name = "account.tax"
    _inherit = ["account.tax", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_tax"


class UomUom(models.Model):
    _name = "uom.uom"
    _inherit = ["uom.uom", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_uom"


class ProductCategory(models.Model):
    _name = "product.category"
    _inherit = ["product.category", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_stock_group"


class StockLocation(models.Model):
    _name = "stock.location"
    _inherit = ["stock.location", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_godown"


class AccountAnalyticAccount(models.Model):
    _name = "account.analytic.account"
    _inherit = ["account.analytic.account", "tally.manual.push.mixin"]

    _tally_enqueue_method = "_enqueue_tally_cost_centre"
