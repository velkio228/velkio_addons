import base64
import logging
import secrets
from datetime import timedelta

import requests
from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

WEBHOOK_TOPICS = (
    "order.created",
    "order.updated",
    "product.created",
    "product.updated",
    "customer.created",
    "customer.updated",
)
WOO_CANCELLED_STATUSES = ("cancelled", "refunded", "failed")
MAX_IMAGE_BYTES = 10 * 1024 * 1024
BATCH_SIZE = 100
# Re-read a few minutes before the last cut-off so clock drift between the
# store and Odoo never drops a record. Imports are idempotent.
INCREMENTAL_OVERLAP = timedelta(minutes=5)


class WooInstance(models.Model):
    _inherit = "woo.instance"

    # Automatic synchronization
    auto_sync = fields.Boolean(string="Automatic Sync")
    sync_interval = fields.Integer(string="Sync Every (minutes)", default=30)
    sync_products = fields.Boolean(string="Import Products", default=True)
    sync_customers = fields.Boolean(string="Import Customers", default=False)
    sync_orders = fields.Boolean(string="Import Orders", default=True)
    sync_stock = fields.Boolean(string="Push Stock", default=True)
    next_auto_sync = fields.Datetime(readonly=True, copy=False)
    last_auto_sync = fields.Datetime(
        readonly=True, copy=False,
        help="Cut-off used for incremental imports. Clear it to re-read every record on the next run.",
    )

    # Catalog
    import_variations = fields.Boolean(default=True)
    import_images = fields.Boolean(default=True)

    # Orders
    order_statuses = fields.Char(
        string="Import Order Statuses",
        default="processing,on-hold,completed",
        required=True,
        help="Comma-separated WooCommerce statuses. Orders in other statuses are imported once they reach one of these.",
    )
    import_shipping = fields.Boolean(string="Import Shipping & Fees", default=True)
    shipping_product_id = fields.Many2one(
        "product.product",
        default=lambda self: self.env.ref("zenvio_woocommerce_connector_pro.product_woo_shipping", raise_if_not_found=False),
    )
    fee_product_id = fields.Many2one(
        "product.product",
        default=lambda self: self.env.ref("zenvio_woocommerce_connector_pro.product_woo_fee", raise_if_not_found=False),
    )
    tax_mode = fields.Selection(
        [
            ("odoo", "Odoo product taxes"),
            ("none", "No taxes"),
            ("mapped", "Map WooCommerce tax rates"),
        ],
        default="odoo",
        required=True,
    )
    salesperson_id = fields.Many2one("res.users", domain="[('share', '=', False)]")
    push_order_status = fields.Boolean(
        default=True,
        help="Confirmed orders become Processing, fully delivered orders Completed and cancelled orders Cancelled in WooCommerce.",
    )
    cancel_on_woo_cancel = fields.Boolean(
        string="Cancel When Cancelled in WooCommerce",
        default=True,
        help="Cancel the Odoo order when the WooCommerce order is cancelled, refunded or failed.",
    )

    # Webhooks
    webhook_secret = fields.Char(copy=False)
    woo_webhook_ids = fields.Char(copy=False, readonly=True)
    webhook_url = fields.Char(compute="_compute_webhook_url")
    webhooks_active = fields.Boolean(compute="_compute_webhook_url")

    variant_mapping_count = fields.Integer(compute="_compute_pro_counts")
    tax_mapping_count = fields.Integer(compute="_compute_pro_counts")

    @api.depends("woo_webhook_ids")
    def _compute_webhook_url(self):
        for instance in self:
            instance.webhook_url = instance.id and f"{instance.get_base_url()}/zenvio/woo/webhook/{instance.id}"
            instance.webhooks_active = bool(instance.woo_webhook_ids)

    def _compute_pro_counts(self):
        for instance in self:
            domain = [("instance_id", "=", instance.id)]
            instance.variant_mapping_count = self.env["woo.variant.mapping"].search_count(domain)
            instance.tax_mapping_count = self.env["woo.tax.mapping"].search_count(domain)

    @api.constrains("sync_interval")
    def _check_sync_interval(self):
        for instance in self:
            if instance.auto_sync and instance.sync_interval < 5:
                raise ValidationError(_("Automatic sync must run at most every 5 minutes."))

    # ------------------------------------------------------------------
    # Automatic synchronization
    # ------------------------------------------------------------------

    @api.model
    def _cron_auto_sync(self):
        now = fields.Datetime.now()
        instances = self.search([
            ("auto_sync", "=", True),
            "|", ("next_auto_sync", "=", False), ("next_auto_sync", "<=", now),
        ])
        for index, instance in enumerate(instances, start=1):
            instance.with_company(instance.company_id)._run_auto_sync()
            # Keep each store's results even if a later store times out.
            self.env["ir.cron"]._commit_progress(1, remaining=len(instances) - index)

    def _run_auto_sync(self):
        self.ensure_one()
        started = fields.Datetime.now()
        params = {}
        if self.last_auto_sync:
            cutoff = self.last_auto_sync - INCREMENTAL_OVERLAP
            params = {"modified_after": cutoff.strftime("%Y-%m-%dT%H:%M:%S"), "dates_are_gmt": "true"}
        counts = {}
        try:
            with self.env.cr.savepoint():
                if self.sync_customers:
                    counts["customers"] = self._import_customers(limit_pages=50)
                if self.sync_products:
                    counts["products"] = self._import_products(params=params, limit_pages=50)
                if self.sync_orders:
                    counts["orders"] = self._import_orders(params=params, limit_pages=50)
                if self.sync_stock:
                    counts["stock"] = self._export_stock()
        except Exception as error:  # noqa: BLE001 - a failing store must not stop the others
            _logger.exception("WooCommerce automatic sync failed for instance %s", self.id)
            self._create_log("auto_sync", state="failed", message=str(error))
        else:
            self.write({"last_auto_sync": started, "last_sync_date": started})
            self._create_log("auto_sync", message=_(
                "Customers: %(customers)s, products: %(products)s, orders: %(orders)s, stock updates: %(stock)s.",
                customers=counts.get("customers", "-"),
                products=counts.get("products", "-"),
                orders=counts.get("orders", "-"),
                stock=counts.get("stock", "-"),
            ))
        self.next_auto_sync = started + timedelta(minutes=max(self.sync_interval, 5))

    def action_run_auto_sync(self):
        for instance in self:
            instance._run_auto_sync()
        return self._reload_notification(_("Synchronization finished. Check the sync logs for details."))

    # ------------------------------------------------------------------
    # Products, variations and images
    # ------------------------------------------------------------------

    def _prepare_product_vals(self, item):
        vals = super()._prepare_product_vals(item)
        if item.get("virtual") or item.get("downloadable"):
            vals["type"] = "service"
        return vals

    def _import_product_item(self, item):
        template = super()._import_product_item(item)
        if not template:
            return template
        if item.get("manage_stock") and template.type == "consu" and not template.is_storable:
            try:
                with self.env.cr.savepoint():
                    template.is_storable = True
            except (UserError, ValidationError) as error:
                _logger.info("Could not track inventory for %s: %s", template.display_name, error)
        if self.import_images:
            self._import_product_image(template, item)
        if self.import_variations and item.get("type") == "variable":
            self._import_variations(template, item)
        return template

    def _import_product_image(self, template, item):
        images = item.get("images") or []
        src = images and images[0].get("src")
        if not src:
            return
        mapping = self.env["woo.product.mapping"].search([
            ("instance_id", "=", self.id), ("woo_id", "=", str(item.get("id"))),
        ], limit=1)
        if mapping.image_src == src and template.image_1920:
            return
        try:
            with requests.get(src, timeout=20, stream=True) as response:
                response.raise_for_status()
                content = response.raw.read(MAX_IMAGE_BYTES + 1, decode_content=True)
        except requests.RequestException as error:
            _logger.warning("Could not download WooCommerce image %s: %s", src, error)
            return
        if not content or len(content) > MAX_IMAGE_BYTES:
            return
        try:
            with self.env.cr.savepoint():
                template.image_1920 = base64.b64encode(content)
        except UserError as error:
            _logger.warning("Ignored invalid WooCommerce image %s: %s", src, error)
            return
        mapping.image_src = src

    def _find_or_create_attribute(self, name):
        Attribute = self.env["product.attribute"]
        attribute = Attribute.search([("name", "ilike", name), ("create_variant", "=", "always")]).filtered(
            lambda a: a.name.lower() == name.lower()
        )[:1]
        return attribute or Attribute.create({"name": name, "create_variant": "always"})

    def _find_or_create_attribute_values(self, attribute, options):
        values = self.env["product.attribute.value"]
        for option in options:
            value = attribute.value_ids.filtered(lambda v: v.name.lower() == option.lower())[:1]
            if not value:
                value = values.create({"attribute_id": attribute.id, "name": option})
            values |= value
        return values

    def _import_variations(self, template, item):
        attributes = [attr for attr in item.get("attributes", []) if attr.get("variation") and attr.get("name")]
        if not attributes:
            return
        variations = self._paged_get(f"products/{item['id']}/variations")
        if not variations:
            return

        for attr in attributes:
            attribute = self._find_or_create_attribute(attr["name"])
            values = self._find_or_create_attribute_values(attribute, attr.get("options") or [])
            line = template.attribute_line_ids.filtered(lambda l: l.attribute_id == attribute)
            if line:
                missing = values - line.value_ids
                if missing:
                    line.value_ids = [Command.link(value.id) for value in missing]
            elif values:
                template.attribute_line_ids = [Command.create({
                    "attribute_id": attribute.id,
                    "value_ids": [Command.set(values.ids)],
                })]

        mapping_model = self.env["woo.variant.mapping"]
        prices = {}
        for variation in variations:
            wanted = {
                (attr["name"].lower(), attr["option"].lower())
                for attr in variation.get("attributes", [])
                if attr.get("name") and attr.get("option")
            }
            variant = template.product_variant_ids.filtered(lambda p: wanted <= {
                (ptav.attribute_id.name.lower(), ptav.name.lower())
                for ptav in p.product_template_attribute_value_ids
            })[:1]
            if not variant:
                continue
            if variation.get("sku"):
                variant.default_code = variation["sku"]
            if variation.get("manage_stock") and not template.is_storable and template.type == "consu":
                template.is_storable = True
            woo_id = str(variation["id"])
            vals = {
                "instance_id": self.id,
                "woo_id": woo_id,
                "woo_parent_id": str(item["id"]),
                "sku": variation.get("sku"),
                "product_id": variant.id,
                "last_sync_date": fields.Datetime.now(),
            }
            mapping = mapping_model.search([("instance_id", "=", self.id), ("woo_id", "=", woo_id)], limit=1)
            if mapping:
                mapping.write(vals)
            else:
                mapping_model.create(vals)
            price = variation.get("regular_price") or variation.get("price")
            if price:
                prices[variant] = float(price)

        # Odoo prices variants as template price + value extras, which can only
        # reproduce WooCommerce prices exactly when one attribute varies.
        if prices and len(attributes) == 1:
            base_price = min(prices.values())
            template.list_price = base_price
            for variant, price in prices.items():
                variant.product_template_attribute_value_ids.price_extra = price - base_price

    # ------------------------------------------------------------------
    # Stock
    # ------------------------------------------------------------------

    def action_export_stock(self):
        for instance in self:
            count = instance._export_stock()
            instance._mark_synced()
            instance._create_log("export_stock", message=_("Updated stock for %s products.") % count)
        return self._reload_notification(_("Stock export completed."))

    def _stock_qty(self, product):
        if self.warehouse_id:
            product = product.with_context(warehouse_id=self.warehouse_id.id)
        return max(int(product.free_qty), 0)

    def _push_stock_batch(self, resource, updates):
        """Send stock updates in batches and return how many WooCommerce accepted."""
        accepted = set()
        errors = []
        for start in range(0, len(updates), BATCH_SIZE):
            chunk = [{"id": int(woo_id), "manage_stock": True, "stock_quantity": qty} for woo_id, qty in updates[start:start + BATCH_SIZE]]
            result = self._woo_request("POST", resource, payload={"update": chunk})
            for row in result.get("update", []):
                if row.get("error"):
                    errors.append(f"#{row.get('id')}: {row['error'].get('message')}")
                else:
                    accepted.add(str(row.get("id")))
        if errors:
            self._create_log("export_stock", state="failed", message="\n".join(errors))
        return accepted

    def _export_stock(self):
        self.ensure_one()
        # Orders imported earlier in the same run may have changed reservations.
        self.env["product.product"].invalidate_model(["qty_available", "free_qty"])
        count = 0
        simple = self.env["woo.product.mapping"].search([("instance_id", "=", self.id)]).filtered(
            lambda m: m.product_tmpl_id.is_storable and m.product_tmpl_id.product_variant_count == 1
        )
        pending = []
        for mapping in simple:
            qty = self._stock_qty(mapping.product_tmpl_id.product_variant_id)
            if qty != mapping.woo_stock_qty:
                pending.append((mapping, qty))
        if pending:
            accepted = self._push_stock_batch("products/batch", [(m.woo_id, qty) for m, qty in pending])
            for mapping, qty in pending:
                if mapping.woo_id in accepted:
                    mapping.woo_stock_qty = qty
                    count += 1

        variants = self.env["woo.variant.mapping"].search([("instance_id", "=", self.id)]).filtered(
            lambda m: m.product_id.is_storable
        )
        by_parent = {}
        for mapping in variants:
            qty = self._stock_qty(mapping.product_id)
            if qty != mapping.woo_stock_qty:
                by_parent.setdefault(mapping.woo_parent_id, []).append((mapping, qty))
        for parent_id, rows in by_parent.items():
            accepted = self._push_stock_batch(f"products/{parent_id}/variations/batch", [(m.woo_id, qty) for m, qty in rows])
            for mapping, qty in rows:
                if mapping.woo_id in accepted:
                    mapping.woo_stock_qty = qty
                    count += 1
        return count

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def _allowed_order_statuses(self):
        return {status.strip() for status in (self.order_statuses or "").split(",") if status.strip()}

    def _import_order_item(self, item):
        woo_id = str(item.get("id") or "")
        if not woo_id:
            return False
        mapping = self.env["woo.sale.order.mapping"].search([("instance_id", "=", self.id), ("woo_id", "=", woo_id)], limit=1)
        if mapping:
            self._update_order_from_woo(mapping, item)
            return False
        if item.get("status") not in self._allowed_order_statuses():
            return False
        # The order already has this status in WooCommerce; don't echo it back.
        return super(WooInstance, self.with_context(woo_skip_status_push=True))._import_order_item(item)

    def _update_order_from_woo(self, mapping, item):
        status = item.get("status")
        if not status or status == mapping.woo_status:
            return
        mapping.write({"woo_status": status, "last_sync_date": fields.Datetime.now()})
        order = mapping.sale_order_id.with_context(woo_skip_status_push=True)
        if status in WOO_CANCELLED_STATUSES and self.cancel_on_woo_cancel and order.state != "cancel":
            try:
                with self.env.cr.savepoint():
                    order._action_cancel()
                order.message_post(body=_("Cancelled because the WooCommerce order is now %s.") % status)
            except (UserError, ValidationError) as error:
                self._create_log("import_orders", state="failed", message=_(
                    "Could not cancel %(order)s: %(error)s", order=order.name, error=error,
                ))
        elif status in ("processing", "completed") and order.state in ("draft", "sent") and self.auto_confirm_orders:
            order.action_confirm()

    def _prepare_order_vals(self, item, partner):
        vals = super()._prepare_order_vals(item, partner)
        self._update_partner_address(partner, item.get("billing") or {})
        shipping = item.get("shipping") or {}
        if shipping.get("address_1"):
            vals["partner_shipping_id"] = self._delivery_partner(partner, shipping).id
        if self.salesperson_id:
            vals["user_id"] = self.salesperson_id.id
        elif self.env.su or self.env.user._is_public():
            # Cron and webhook imports run as a technical user.
            vals["user_id"] = False
        return vals

    def _address_vals(self, data):
        country = self.env["res.country"].search([("code", "=", (data.get("country") or "").upper())], limit=1) if data.get("country") else False
        state = False
        if country and data.get("state"):
            state = self.env["res.country.state"].search([
                ("country_id", "=", country.id), ("code", "=", data["state"].upper()),
            ], limit=1)
        return {
            "street": data.get("address_1") or False,
            "street2": data.get("address_2") or False,
            "city": data.get("city") or False,
            "zip": data.get("postcode") or False,
            "country_id": country.id if country else False,
            "state_id": state.id if state else False,
        }

    def _update_partner_address(self, partner, billing):
        if billing.get("address_1") and not partner.street:
            vals = self._address_vals(billing)
            if billing.get("company") and not partner.company_name:
                vals["company_name"] = billing["company"]
            partner.write(vals)

    def _delivery_partner(self, partner, shipping):
        vals = self._address_vals(shipping)
        if vals["street"] == partner.street and vals["zip"] == partner.zip:
            return partner
        existing = partner.child_ids.filtered(
            lambda c: c.type == "delivery" and c.street == vals["street"] and c.zip == vals["zip"]
        )[:1]
        if existing:
            return existing
        name = f"{shipping.get('first_name') or ''} {shipping.get('last_name') or ''}".strip()
        return self.env["res.partner"].create(dict(
            vals,
            type="delivery",
            parent_id=partner.id,
            name=name or partner.name,
            phone=shipping.get("phone") or False,
        ))

    def _product_from_order_line(self, line):
        variation_id = str(line.get("variation_id") or "")
        if variation_id and variation_id != "0":
            mapping = self.env["woo.variant.mapping"].search([
                ("instance_id", "=", self.id), ("woo_id", "=", variation_id),
            ], limit=1)
            if mapping:
                return mapping.product_id
        return super()._product_from_order_line(line)

    def _taxes_for_woo_line(self, line, unmapped):
        """Return the Odoo taxes for a WooCommerce line, or None to keep Odoo defaults."""
        if self.tax_mode == "odoo":
            return None
        taxes = self.env["account.tax"]
        if self.tax_mode == "none":
            return taxes
        rate_ids = [str(tax["id"]) for tax in line.get("taxes", []) if tax.get("total") not in (None, "", "0", "0.00")]
        mappings = self.env["woo.tax.mapping"].search([("instance_id", "=", self.id), ("woo_id", "in", rate_ids)])
        for rate_id in rate_ids:
            mapping = mappings.filtered(lambda m: m.woo_id == rate_id)
            if mapping.tax_id:
                taxes |= mapping.tax_id
            else:
                unmapped.add(rate_id)
        return taxes

    def _prepare_order_line_vals(self, sale_order, line):
        vals = super()._prepare_order_line_vals(sale_order, line)
        taxes = self._taxes_for_woo_line(line, self.env.context.get("woo_unmapped_taxes", set()))
        if taxes is not None:
            vals["tax_ids"] = [Command.set(taxes.ids)]
        return vals

    def _create_order_lines(self, sale_order, item):
        unmapped = set()
        instance = self.with_context(woo_unmapped_taxes=unmapped)
        super(WooInstance, instance)._create_order_lines(sale_order, item)
        if self.import_shipping:
            extra = [
                (self.shipping_product_id, line.get("method_title"), line)
                for line in item.get("shipping_lines", [])
            ] + [
                (self.fee_product_id, line.get("name"), line)
                for line in item.get("fee_lines", [])
            ]
            for product, label, line in extra:
                if not product:
                    continue
                vals = {
                    "order_id": sale_order.id,
                    "product_id": product.id,
                    "name": label or product.display_name,
                    "product_uom_qty": 1.0,
                    "price_unit": float(line.get("total") or 0.0),
                }
                taxes = instance._taxes_for_woo_line(line, unmapped)
                if taxes is not None:
                    vals["tax_ids"] = [Command.set(taxes.ids)]
                self.env["sale.order.line"].create(vals)

        notes = []
        coupons = [coupon.get("code") for coupon in item.get("coupon_lines", []) if coupon.get("code")]
        if coupons:
            notes.append(_("Coupons applied in WooCommerce (already included in line prices): %s") % ", ".join(coupons))
        if item.get("payment_method_title"):
            notes.append(_("Payment method: %s") % item["payment_method_title"])
        if item.get("customer_note"):
            notes.append(_("Customer note: %s") % item["customer_note"])
        if unmapped:
            notes.append(_("WooCommerce tax rates without an Odoo tax (lines imported without them): %s") % ", ".join(sorted(unmapped)))
        if notes:
            sale_order.message_post(body=Markup("<br/>").join(notes))

    # ------------------------------------------------------------------
    # Taxes
    # ------------------------------------------------------------------

    def action_import_tax_rates(self):
        self.ensure_one()
        mapping_model = self.env["woo.tax.mapping"]
        for rate in self._paged_get("taxes"):
            woo_id = str(rate.get("id") or "")
            if not woo_id:
                continue
            location = " ".join(filter(None, [rate.get("country"), rate.get("state")]))
            vals = {
                "name": f"{rate.get('name') or _('Tax')} ({location})" if location else (rate.get("name") or _("Tax")),
                "rate": float(rate.get("rate") or 0.0),
            }
            mapping = mapping_model.search([("instance_id", "=", self.id), ("woo_id", "=", woo_id)], limit=1)
            if mapping:
                mapping.write(vals)
                continue
            tax = self.env["account.tax"].search([
                ("type_tax_use", "=", "sale"),
                ("amount_type", "=", "percent"),
                ("amount", "=", vals["rate"]),
                ("company_id", "parent_of", self.company_id.id),
            ]).filtered(lambda t: not t.price_include)[:1]
            mapping_model.create(dict(vals, instance_id=self.id, woo_id=woo_id, tax_id=tax.id))
        self._create_log("import_taxes", message=_("Tax rates refreshed. Review the mappings before importing orders."))
        return self.action_view_tax_mappings()

    def action_view_tax_mappings(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("zenvio_woocommerce_connector_pro.action_woo_tax_mapping")
        action["domain"] = [("instance_id", "=", self.id)]
        action["context"] = {"default_instance_id": self.id}
        return action

    def action_view_variant_mappings(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("zenvio_woocommerce_connector_pro.action_woo_variant_mapping")
        action["domain"] = [("instance_id", "=", self.id)]
        return action

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def action_register_webhooks(self):
        for instance in self:
            if not instance.webhook_url.startswith("https://"):
                raise UserError(_(
                    "WooCommerce delivers webhooks only to a public HTTPS address. "
                    "Set the Odoo web.base.url system parameter to your https:// domain first."
                ))
            instance._delete_webhooks()
            if not instance.webhook_secret:
                instance.webhook_secret = secrets.token_urlsafe(32)
            ids = []
            for topic in WEBHOOK_TOPICS:
                result = instance._woo_request("POST", "webhooks", payload={
                    "name": f"Odoo - {instance.name} - {topic}",
                    "topic": topic,
                    "delivery_url": instance.webhook_url,
                    "secret": instance.webhook_secret,
                    "status": "active",
                })
                ids.append(str(result.get("id")))
            instance.woo_webhook_ids = ",".join(ids)
            instance._create_log("register_webhooks", message=_("Registered %s webhooks.") % len(ids))
        return self._reload_notification(_("Webhooks registered. WooCommerce will now push changes in real time."))

    def action_unregister_webhooks(self):
        for instance in self:
            instance._delete_webhooks()
            instance._create_log("register_webhooks", message=_("Webhooks removed."))
        return self._reload_notification(_("Webhooks removed."))

    def _delete_webhooks(self):
        self.ensure_one()
        for webhook_id in filter(None, (self.woo_webhook_ids or "").split(",")):
            try:
                self._woo_request("DELETE", f"webhooks/{webhook_id}", params={"force": "true"})
            except UserError as error:
                # Already deleted in WooCommerce.
                _logger.info("Could not delete WooCommerce webhook %s: %s", webhook_id, error)
        self.woo_webhook_ids = False

    def _process_webhook(self, topic, payload):
        self.ensure_one()
        resource = (topic or "").partition(".")[0]
        handlers = {
            "order": self._import_order_item,
            "product": self._import_product_item,
            "customer": self._import_customer_item,
        }
        handler = handlers.get(resource)
        if not handler or not payload.get("id"):
            return
        if resource == "product" and payload.get("parent_id"):
            return  # Variations are refreshed with their parent product.
        try:
            with self.env.cr.savepoint():
                handler(payload)
                self._mark_synced()
        except Exception as error:  # noqa: BLE001 - always acknowledge so WooCommerce keeps the webhook active
            _logger.exception("WooCommerce webhook %s failed for instance %s", topic, self.id)
            self._create_log("webhook", state="failed", name=topic, message=_(
                "%(topic)s #%(id)s: %(error)s", topic=topic, id=payload.get("id"), error=error,
            ))
