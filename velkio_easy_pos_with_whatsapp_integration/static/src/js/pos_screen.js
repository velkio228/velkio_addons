/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { useDebounced } from "@web/core/utils/timing";
import { KeepLast } from "@web/core/utils/concurrency";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const MODEL = "pos.screen.order";

export class PosScreen extends Component {
    static template = "velkio_easy_pos_with_whatsapp_integration.PosScreen";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");

        // One in-flight request per search box; late replies are dropped so a
        // slow query can never overwrite the results of a newer one.
        this.productKeeper = new KeepLast();
        this.partnerKeeper = new KeepLast();
        this.totalsKeeper = new KeepLast();

        this.searchInput = useRef("searchInput");
        this.partnerInput = useRef("partnerInput");
        this.lineKey = 1;

        this.state = useState({
            loading: true,
            saving: false,
            companyId: false,
            currency: { id: false, symbol: "", position: "before", decimal_places: 2 },

            orderId: null,
            orderName: "",
            orderState: "draft",

            query: "",
            results: [],
            searching: false,
            highlight: 0,
            showResults: false,

            partner: null,
            partnerQuery: "",
            partnerResults: [],
            partnerHighlight: 0,
            showPartnerResults: false,
            pricelistId: false,
            pricelistName: "",

            lines: [],

            amountUntaxed: 0,
            amountTax: 0,
            amountTotal: 0,
            amountGross: 0,
            amountDiscount: 0,
            taxBreakup: [],
            userName: "",

            configs: [],
            configId: false,
            config: null,
            columns: [],
            company: {},

            paymentMethodId: false,
            paymentMethods: [],
            note: "",
            whatsappNumber: "",
            billTime: "",

            drafts: [],
            showDrafts: false,
            dirty: false,

            flash: null,
            showNote: false,
        });

        this.state.billTime = this.nowLabel();

        this.searchProductsDebounced = useDebounced(() => this.searchProducts(), 200);
        this.searchPartnersDebounced = useDebounced(() => this.searchPartners(), 250);
        this.recomputeDebounced = useDebounced(() => this.recompute(), 150);

        onWillStart(async () => {
            await this.loadScreenConfig();

            const params = (this.props.action && this.props.action.params) || {};
            if (params.order_id) {
                await this.loadOrder(params.order_id);
            }
            await this.loadDrafts();
            this.state.loading = false;
        });

        onMounted(() => this.focusSearch());
        onWillUnmount(() => clearTimeout(this.flashTimer));
    }

    // ------------------------------------------------------------------
    // Counter configuration
    // ------------------------------------------------------------------
    async loadScreenConfig(configId = false) {
        const data = await this.orm.call(MODEL, "get_screen_config", [], {
            config_id: configId || this.state.configId || false,
        });
        this.state.companyId = data.company_id;
        this.state.userName = data.user_name || "";
        this.state.configs = data.configs || [];
        this.state.company = {
            name: data.company_name || "",
            address: data.company_address || "",
            phone: data.company_phone || "",
            vat: data.company_vat || "",
        };

        const config = data.config;
        this.state.config = config || null;
        if (config) {
            this.state.configId = config.id;
            this.state.columns = config.columns || [];
            this.state.paymentMethods = config.payment_methods || [];
            this.state.currency = config.currency || data.currency;
            if (!this.state.pricelistId && config.pricelist_id) {
                this.state.pricelistId = config.pricelist_id;
                this.state.pricelistName = config.pricelist_name || "";
            }
            // keep a valid payment method selected
            const known = this.state.paymentMethods.some(
                (m) => m.id === this.state.paymentMethodId
            );
            if (!known) {
                this.state.paymentMethodId =
                    this.state.paymentMethods.length
                        ? this.state.paymentMethods[0].id
                        : false;
            }
        } else {
            this.state.columns = [];
            this.state.paymentMethods = [];
            this.state.currency = data.currency;
        }
    }

    async switchConfig(ev) {
        const configId = parseInt(ev.target.value, 10);
        if (!configId || configId === this.state.configId) {
            return;
        }
        const apply = async () => {
            this.state.configId = configId;
            await this.loadScreenConfig(configId);
            await this.refreshPricing();
            await this.searchProducts();
        };
        if (!this.state.dirty) {
            await apply();
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Switch counter?"),
            body: _t("This bill has unsaved changes and will be discarded."),
            confirmLabel: _t("Switch"),
            confirm: async () => {
                this.resetOrder();
                await apply();
            },
            cancel: () => {},
        });
    }

    get configName() {
        return this.state.config ? this.state.config.name : "";
    }

    get paymentMethod() {
        return this.state.paymentMethods.find(
            (m) => m.id === this.state.paymentMethodId
        );
    }

    // ------------------------------------------------------------------
    // Formatting helpers
    // ------------------------------------------------------------------
    formatMoney(value) {
        return formatMonetary(value || 0, { currencyId: this.state.currency.id });
    }

    /**
     * Confirmation shown inside the billing panel, beside the buttons that
     * triggered it. Odoo's notification service anchors top-right, where it
     * covers this screen's own toolbar.
     */
    showFlash(text, type = "success") {
        this.state.flash = { text, type };
        clearTimeout(this.flashTimer);
        this.flashTimer = setTimeout(() => {
            this.state.flash = null;
        }, 4000);
    }

    /** Local, human date for the receipt header. */
    nowLabel(value) {
        // Odoo sends naive UTC ("2026-09-16 07:26:00"); mark it as UTC so the
        // browser renders it in the viewer's own timezone.
        const date = value ? new Date(value.replace(" ", "T") + "Z") : new Date();
        return date.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    get hasDiscount() {
        return (this.state.amountDiscount || 0) > 0;
    }

    formatQty(value) {
        const rounded = Math.round((value || 0) * 1000) / 1000;
        return String(rounded);
    }

    stockClass(line) {
        if (!line.tracks_stock) {
            return "o_pos_screen_stock_na";
        }
        if ((line.qty_available || 0) <= 0) {
            return "o_pos_screen_stock_out";
        }
        if ((line.qty_available || 0) < (line.qty || 0)) {
            return "o_pos_screen_stock_low";
        }
        return "o_pos_screen_stock_ok";
    }

    get cartPayload() {
        return {
            company_id: this.state.companyId,
            partner_id: this.state.partner ? this.state.partner.id : false,
            pricelist_id: this.state.pricelistId || false,
            lines: this.state.lines.map((line) => ({
                key: line.key,
                product_id: line.product_id,
                qty: line.qty,
                price_unit: line.price_unit,
                discount: line.discount,
                tax_ids: line.tax_ids,
            })),
        };
    }

    get totalQty() {
        return this.state.lines.reduce((sum, line) => sum + (line.qty || 0), 0);
    }

    get isEditable() {
        return this.state.orderState === "draft";
    }

    get canPay() {
        return ["draft", "confirmed"].includes(this.state.orderState);
    }

    // ------------------------------------------------------------------
    // Product search
    // ------------------------------------------------------------------
    focusSearch() {
        if (this.searchInput.el) {
            this.searchInput.el.focus();
            this.searchInput.el.select();
        }
    }

    async searchProducts() {
        // Nothing is listed until the cashier actually types something.
        if (!this.state.query.trim()) {
            this.state.results = [];
            this.state.showResults = false;
            this.state.searching = false;
            return;
        }
        this.state.searching = true;
        try {
            const result = await this.productKeeper.add(
                this.orm.call(MODEL, "search_products", [], {
                    query: this.state.query,
                    limit: 20,
                    pricelist_id: this.state.pricelistId || false,
                    partner_id: this.state.partner ? this.state.partner.id : false,
                    company_id: this.state.companyId,
                    config_id: this.state.configId || false,
                })
            );
            this.state.results = result.products;
            this.state.columns = result.columns || this.state.columns;
            this.state.highlight = 0;
            this.state.showResults = true;
        } catch (error) {
            this.state.results = [];
            throw error;
        } finally {
            this.state.searching = false;
        }
    }

    onQueryInput(ev) {
        this.state.query = ev.target.value;
        this.state.showResults = Boolean(this.state.query.trim());
        this.searchProductsDebounced();
    }

    onSearchKeydown(ev) {
        const results = this.state.results;
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                if (results.length) {
                    this.state.showResults = true;
                    this.state.highlight = (this.state.highlight + 1) % results.length;
                    this.scrollHighlightIntoView();
                }
                break;
            case "ArrowUp":
                ev.preventDefault();
                if (results.length) {
                    this.state.highlight =
                        (this.state.highlight - 1 + results.length) % results.length;
                    this.scrollHighlightIntoView();
                }
                break;
            case "Enter": {
                ev.preventDefault();
                const product = results[this.state.highlight];
                if (product) {
                    this.addProduct(product);
                }
                break;
            }
            case "Escape":
                ev.preventDefault();
                this.state.showResults = false;
                break;
        }
    }

    scrollHighlightIntoView() {
        // Deferred so the DOM reflects the new highlight index first.
        setTimeout(() => {
            const el = document.querySelector(".o_pos_screen_result.o_highlighted");
            if (el) {
                el.scrollIntoView({ block: "nearest" });
            }
        });
    }

    // ------------------------------------------------------------------
    // Customer search
    // ------------------------------------------------------------------
    /** Mirror of _normalize_phone() on the server. */
    normalizePhone(value) {
        const raw = (value || "").trim();
        if (!raw || /[a-zA-Z]/.test(raw)) {
            return "";
        }
        const digits = raw.replace(/\D/g, "");
        if (digits.length < 7 || digits.length > 15) {
            return "";
        }
        return raw.startsWith("+") ? "+" + digits : digits;
    }

    get typedNumber() {
        return this.normalizePhone(this.state.partnerQuery);
    }

    /** Take the typed number as the customer, reusing a contact if one matches. */
    async usePartnerNumber() {
        const number = this.typedNumber;
        if (!number) {
            return;
        }
        const partner = await this.orm.call(
            MODEL, "find_or_create_partner_by_number", [], { number }
        );
        await this.selectPartner(partner);
        this.showFlash(
            partner.created
                ? _t("New customer %s created.", partner.display_name)
                : _t("Matched existing customer %s.", partner.display_name),
            "info"
        );
    }

    async searchPartners() {
        try {
            const partners = await this.partnerKeeper.add(
                this.orm.call(MODEL, "search_partners", [], {
                    query: this.state.partnerQuery,
                    limit: 10,
                })
            );
            this.state.partnerResults = partners;
            this.state.partnerHighlight = 0;
            this.state.showPartnerResults = true;
        } catch (error) {
            this.state.partnerResults = [];
            throw error;
        }
    }

    onPartnerInput(ev) {
        this.state.partnerQuery = ev.target.value;
        this.searchPartnersDebounced();
    }

    onPartnerKeydown(ev) {
        const results = this.state.partnerResults;
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                if (results.length) {
                    this.state.partnerHighlight =
                        (this.state.partnerHighlight + 1) % results.length;
                }
                break;
            case "ArrowUp":
                ev.preventDefault();
                if (results.length) {
                    this.state.partnerHighlight =
                        (this.state.partnerHighlight - 1 + results.length) % results.length;
                }
                break;
            case "Enter": {
                ev.preventDefault();
                const partner = results[this.state.partnerHighlight];
                if (partner) {
                    this.selectPartner(partner);
                } else if (this.typedNumber) {
                    this.usePartnerNumber();
                }
                break;
            }
            case "Escape":
                ev.preventDefault();
                this.state.showPartnerResults = false;
                break;
        }
    }

    async selectPartner(partner) {
        this.state.partner = partner;
        this.state.partnerQuery = "";
        this.state.partnerResults = [];
        this.state.showPartnerResults = false;
        this.state.pricelistId = partner.pricelist_id || false;
        this.state.pricelistName = partner.pricelist_name || "";
        await this.refreshPricing();
        await this.searchProducts();
    }

    async clearPartner() {
        this.state.partner = null;
        this.state.pricelistId = false;
        this.state.pricelistName = "";
        await this.refreshPricing();
        await this.searchProducts();
    }

    /** Re-price the whole cart after the customer or pricelist changed. */
    async refreshPricing() {
        this.state.dirty = true;
        if (!this.state.lines.length) {
            this.recomputeDebounced();
            return;
        }
        const updates = await this.orm.call(MODEL, "refresh_cart_pricing", [], {
            payload: this.cartPayload,
        });
        const byKey = new Map(updates.map((u) => [u.key, u]));
        let changed = 0;
        for (const line of this.state.lines) {
            const update = byKey.get(line.key);
            if (!update) {
                continue;
            }
            if (line.price_unit !== update.price_unit) {
                changed++;
            }
            line.price_unit = update.price_unit;
            line.tax_ids = update.tax_ids;
            line.tax_names = update.tax_names;
        }
        if (changed) {
            this.showFlash(
                _t("%s line(s) re-priced for this customer.", changed),
                "info"
            );
        }
        this.recomputeDebounced();
    }

    // ------------------------------------------------------------------
    // Cart
    // ------------------------------------------------------------------
    async addProduct(product) {
        if (!this.isEditable) {
            return;
        }
        const existing = this.state.lines.find((l) => l.product_id === product.id);
        if (existing) {
            existing.qty += 1;
            this.afterCartChange();
            this.focusSearch();
            return;
        }
        const defaults = await this.orm.call(MODEL, "get_product_defaults", [], {
            product_id: product.id,
            qty: 1.0,
            pricelist_id: this.state.pricelistId || false,
            partner_id: this.state.partner ? this.state.partner.id : false,
            company_id: this.state.companyId,
        });
        this.state.lines.push({
            key: this.lineKey++,
            product_id: defaults.product_id,
            name: defaults.name,
            default_code: product.default_code || "",
            uom_id: defaults.uom_id,
            uom_name: defaults.uom_name,
            qty: 1.0,
            price_unit: defaults.price_unit,
            discount: 0.0,
            tax_ids: defaults.tax_ids,
            tax_names: defaults.tax_names,
            qty_available: defaults.qty_available,
            tracks_stock: defaults.tracks_stock,
            image_url: defaults.image_url,
            price_subtotal: 0,
            price_total: 0,
        });
        this.afterCartChange();
        this.focusSearch();
    }

    afterCartChange() {
        // Clear the box and the suggestions so the next scan/type starts fresh.
        this.state.query = "";
        this.state.results = [];
        this.state.showResults = false;
        this.markDirty();
    }

    /** Any change the cashier has not saved yet. */
    markDirty() {
        this.state.dirty = true;
        this.recomputeDebounced();
    }

    setPayment(methodId) {
        this.state.paymentMethodId = methodId;
        this.state.dirty = true;
    }

    toggleNote() {
        this.state.showNote = !this.state.showNote;
    }

    setNote(ev) {
        this.state.note = ev.target.value;
        this.state.dirty = true;
    }

    onQtyInput(line, ev) {
        const value = parseFloat(ev.target.value);
        line.qty = Number.isFinite(value) ? value : 0;
        this.markDirty();
    }

    onPriceInput(line, ev) {
        const value = parseFloat(ev.target.value);
        line.price_unit = Number.isFinite(value) ? value : 0;
        this.markDirty();
    }

    onDiscountInput(line, ev) {
        let value = parseFloat(ev.target.value);
        if (!Number.isFinite(value)) {
            value = 0;
        }
        line.discount = Math.min(Math.max(value, 0), 100);
        this.markDirty();
    }

    stepQty(line, delta) {
        line.qty = Math.max((line.qty || 0) + delta, 0);
        this.markDirty();
    }

    removeLine(line) {
        const index = this.state.lines.findIndex((l) => l.key === line.key);
        if (index >= 0) {
            this.state.lines.splice(index, 1);
        }
        this.markDirty();
    }

    async recompute() {
        if (!this.state.lines.length) {
            this.state.amountUntaxed = 0;
            this.state.amountTax = 0;
            this.state.amountTotal = 0;
            this.state.amountGross = 0;
            this.state.amountDiscount = 0;
            this.state.taxBreakup = [];
            return;
        }
        const result = await this.totalsKeeper.add(
            this.orm.call(MODEL, "compute_cart", [], { payload: this.cartPayload })
        );
        const byKey = new Map(result.lines.map((l) => [l.key, l]));
        for (const line of this.state.lines) {
            const computed = byKey.get(line.key);
            if (computed) {
                line.price_subtotal = computed.price_subtotal;
                line.price_total = computed.price_total;
            }
        }
        this.state.amountUntaxed = result.amount_untaxed;
        this.state.amountTax = result.amount_tax;
        this.state.amountTotal = result.amount_total;
        this.state.amountGross = result.amount_gross;
        this.state.amountDiscount = result.amount_discount;
        this.state.taxBreakup = result.tax_breakup;
        this.state.currency = result.currency;
    }

    // ------------------------------------------------------------------
    // Receipt
    // ------------------------------------------------------------------
    /** Freeze what is on screen into a plain object the receipt renders from. */
    buildReceipt(saved = {}) {
        const method = this.paymentMethod;
        return {
            name: saved.name || this.state.orderName || "",
            date: this.state.billTime,
            cashier: this.state.userName,
            counter: this.configName,
            customer: this.state.partner ? this.state.partner.display_name : "",
            pickingName: saved.picking_name || "",
            lines: this.state.lines.map((l) => ({
                name: l.name,
                code: l.default_code || "",
                qty: l.qty,
                uom: l.uom_name || "",
                price: l.price_unit,
                discount: l.discount,
                subtotal: l.price_subtotal,
            })),
            amountGross: this.state.amountGross,
            amountDiscount: this.state.amountDiscount,
            amountUntaxed: this.state.amountUntaxed,
            taxBreakup: this.state.taxBreakup.slice(),
            amountTotal: this.state.amountTotal,
            payment: method ? method.name : "",
            machine: method ? method.machine_name : "",
        };
    }

    get canPrint() {
        return Boolean(this.lastReceipt || this.state.lines.length);
    }

    /**
     * Print through a hidden iframe rather than window.print(): the backend
     * carries its own print stylesheet, and an iframe keeps the receipt
     * completely isolated from it.
     */
    printReceipt() {
        const receipt = this.lastReceipt || this.buildReceipt();
        if (!receipt.lines.length) {
            this.showFlash(_t("Nothing to print."), "warning");
            return;
        }
        const frame = document.createElement("iframe");
        frame.setAttribute("aria-hidden", "true");
        Object.assign(frame.style, {
            position: "fixed",
            right: "0",
            bottom: "0",
            width: "0",
            height: "0",
            border: "0",
        });
        document.body.appendChild(frame);

        const cleanup = () => frame.remove();
        frame.contentWindow.addEventListener("afterprint", cleanup);

        const doc = frame.contentWindow.document;
        doc.open();
        doc.write(this.receiptHtml(receipt));
        doc.close();

        // Give the iframe a tick to lay out before printing.
        setTimeout(() => {
            try {
                frame.contentWindow.focus();
                frame.contentWindow.print();
            } catch {
                cleanup();
                this.showFlash(_t("Could not open the print dialog."), "warning");
            }
            // Safety net for browsers that never fire afterprint.
            setTimeout(cleanup, 60000);
        }, 60);
    }

    receiptHtml(receipt) {
        const cfg = (this.state.config && this.state.config.receipt) || {};
        const paper = cfg.paper || "80";
        const widths = { 80: "72mm", 58: "50mm", a4: "190mm" };
        const width = widths[paper] || "72mm";
        const company = this.state.company || {};
        const esc = (v) =>
            String(v === undefined || v === null ? "" : v).replace(
                /[&<>"']/g,
                (c) =>
                    ({
                        "&": "&amp;",
                        "<": "&lt;",
                        ">": "&gt;",
                        '"': "&quot;",
                        "'": "&#39;",
                    }[c])
            );
        const money = (v) => esc(this.formatMoney(v));
        const row = (label, value, cls = "") =>
            `<tr class="${cls}"><td>${esc(label)}</td><td class="r">${value}</td></tr>`;

        const lines = receipt.lines
            .map(
                (l) => `
      <tr class="item">
        <td colspan="2">${esc(l.code ? l.code + " " : "")}${esc(l.name)}</td>
      </tr>
      <tr>
        <td class="qty">${esc(this.formatQty(l.qty))} ${esc(l.uom)} x ${money(l.price)}${
                    l.discount ? ` <span class="disc">-${esc(l.discount)}%</span>` : ""
                }</td>
        <td class="r">${money(l.subtotal)}</td>
      </tr>`
            )
            .join("");

        const taxes =
            cfg.show_tax_breakup !== false
                ? receipt.taxBreakup
                      .map((t) => row(t.name, money(t.amount), "muted"))
                      .join("")
                : "";

        return `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(receipt.name || "Receipt")}</title>
<style>
  @page { size: ${paper === "a4" ? "A4" : width + " auto"}; margin: ${
            paper === "a4" ? "12mm" : "3mm"
        }; }
  * { box-sizing: border-box; }
  body { width: ${width}; margin: 0 auto; padding: 0;
         font-family: "DejaVu Sans Mono", "Courier New", monospace;
         font-size: ${paper === "58" ? "10px" : "11px"}; color: #000; }
  .c { text-align: center; }
  .r { text-align: right; white-space: nowrap; }
  .b { font-weight: bold; }
  .muted { color: #444; }
  h1 { font-size: ${paper === "58" ? "13px" : "15px"}; margin: 0 0 2px; text-align: center; }
  .sub { text-align: center; font-size: 10px; line-height: 1.35; }
  hr { border: 0; border-top: 1px dashed #000; margin: 6px 0; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 1px 0; vertical-align: top; }
  .item td { padding-top: 4px; font-weight: bold; }
  .qty { padding-left: 6px; color: #333; }
  .disc { font-weight: bold; }
  .total td { font-size: ${paper === "58" ? "13px" : "15px"}; font-weight: bold;
              padding-top: 4px; border-top: 1px solid #000; }
  .meta td { font-size: 10px; }
  .foot { text-align: center; margin-top: 8px; font-size: 10px; white-space: pre-line; }
</style></head><body>
  <h1>${esc(company.name)}</h1>
  <div class="sub">${esc(company.address)}${
            company.phone ? "<br>Ph: " + esc(company.phone) : ""
        }${company.vat ? "<br>GSTIN: " + esc(company.vat) : ""}</div>
  ${cfg.header ? `<div class="sub" style="white-space:pre-line">${esc(cfg.header)}</div>` : ""}
  <hr>
  <table class="meta">
    ${row("Bill", esc(receipt.name))}
    ${row("Date", esc(receipt.date))}
    ${row("Counter", esc(receipt.counter))}
    ${row("Cashier", esc(receipt.cashier))}
    ${receipt.customer ? row("Customer", esc(receipt.customer)) : ""}
  </table>
  <hr>
  <table>${lines}</table>
  <hr>
  <table>
    ${
        receipt.amountDiscount > 0
            ? row("Gross", money(receipt.amountGross)) +
              row("Discount", "-" + money(receipt.amountDiscount))
            : ""
    }
    ${row("Untaxed", money(receipt.amountUntaxed))}
    ${taxes}
    <tr class="total"><td>TOTAL</td><td class="r">${money(receipt.amountTotal)}</td></tr>
  </table>
  <hr>
  <table class="meta">
    ${row("Paid by", esc(receipt.payment))}
    ${receipt.machine ? row("Machine", esc(receipt.machine)) : ""}
    ${receipt.pickingName ? row("Delivery", esc(receipt.pickingName)) : ""}
  </table>
  <div class="foot">${esc(cfg.footer || "")}</div>
</body></html>`;
    }

    // ------------------------------------------------------------------
    // Persistence
    // ------------------------------------------------------------------
    async loadDrafts() {
        this.state.drafts = await this.orm.call(MODEL, "get_draft_orders", [], {
            limit: 20,
        });
    }

    async toggleDrafts() {
        this.state.showDrafts = !this.state.showDrafts;
        if (this.state.showDrafts) {
            await this.loadDrafts();
        }
    }

    closeDrafts() {
        this.state.showDrafts = false;
    }

    /** Pull a parked bill back onto the screen. */
    async openDraft(draft) {
        const proceed = async () => {
            this.state.showDrafts = false;
            await this.loadOrder(draft.id);
            this.focusSearch();
        };
        if (!this.state.dirty) {
            await proceed();
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Discard the current bill?"),
            body: _t(
                "This bill has unsaved changes. Opening %s will lose them.",
                draft.name
            ),
            confirmLabel: _t("Discard and open"),
            confirm: () => proceed(),
            cancel: () => {},
        });
    }

    async loadOrder(orderId) {
        const data = await this.orm.call(MODEL, "load_order", [], { order_id: orderId });
        this.state.orderId = data.order_id;
        this.state.orderName = data.name;
        this.state.orderState = data.state;
        this.state.billTime = this.nowLabel(data.date_order);
        this.state.companyId = data.company_id;
        this.state.currency = data.currency;
        if (data.config_id && data.config_id !== this.state.configId) {
            await this.loadScreenConfig(data.config_id);
        }
        if (data.payment_method_id) {
            this.state.paymentMethodId = data.payment_method_id;
        }
        this.state.note = data.note || "";
        this.state.whatsappNumber = data.whatsapp_number_manual || "";
        this.state.showNote = Boolean(data.note);
        this.state.pricelistId = data.pricelist_id || false;
        this.state.pricelistName = data.pricelist_name || "";
        this.state.partner = data.partner_id
            ? { id: data.partner_id, display_name: data.partner_name }
            : null;
        this.state.lines = data.lines.map((line) => ({
            key: this.lineKey++,
            ...line,
            price_subtotal: 0,
            price_total: 0,
        }));
        await this.recompute();
        this.state.dirty = false;
    }

    async sendWhatsApp() {
        const action = await this.orm.call(MODEL, "action_send_whatsapp", [[this.state.orderId]]);
        await this.action.doAction(action);
    }

    async save({ confirm = false, paid = false } = {}) {
        if (!this.state.lines.length) {
            this.showFlash(_t("Add at least one product first."), "warning");
            return;
        }
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = {
                ...this.cartPayload,
                order_id: this.state.orderId || false,
                config_id: this.state.configId || false,
                payment_method_id: this.state.paymentMethodId || false,
                note: this.state.note,
                whatsapp_number: this.state.whatsappNumber,
                confirm,
                paid,
            };
            payload.lines = this.state.lines.map((line) => ({
                product_id: line.product_id,
                name: line.name,
                uom_id: line.uom_id,
                qty: line.qty,
                price_unit: line.price_unit,
                discount: line.discount,
                tax_ids: line.tax_ids,
            }));
            const result = await this.orm.call(MODEL, "create_from_ui", [], { payload });
            this.state.orderId = result.order_id;
            this.state.orderName = result.name;
            this.state.orderState = result.state;
            let message = _t("%(name)s saved - %(total)s", {
                name: result.name,
                total: this.formatMoney(result.amount_total),
            });
            // The integrated WhatsApp queue returns the receipt status.
            if (result.whatsapp_status) {
                message += " \u00b7 " + result.whatsapp_status;
            }
            this.showFlash(message);
            this.state.dirty = false;

            // Snapshot before resetOrder() clears the cart, and re-attach it
            // afterwards - resetOrder() drops the previous receipt on purpose.
            const receipt = paid ? this.buildReceipt(result) : null;
            if (paid || confirm) {
                this.resetOrder();
            }
            if (receipt) {
                this.lastReceipt = receipt;
                if (this.state.config && this.state.config.receipt.auto_print) {
                    this.printReceipt();
                }
            }
            await this.loadDrafts();
        } finally {
            this.state.saving = false;
        }
    }

    resetOrder() {
        this.state.orderId = null;
        this.state.orderName = "";
        this.state.orderState = "draft";
        this.state.lines = [];
        this.state.note = "";
        this.state.whatsappNumber = "";
        this.state.showNote = false;
        this.state.paymentMethodId = this.state.paymentMethods.length
            ? this.state.paymentMethods[0].id
            : false;
        this.state.query = "";
        this.state.amountUntaxed = 0;
        this.state.amountTax = 0;
        this.state.amountTotal = 0;
        this.state.amountGross = 0;
        this.state.amountDiscount = 0;
        this.state.taxBreakup = [];
        this.state.results = [];
        this.state.showResults = false;
        this.state.billTime = this.nowLabel();
        this.state.dirty = false;
        this.lastReceipt = null;
        this.focusSearch();
    }

    onNewOrder() {
        if (!this.state.dirty) {
            this.resetOrder();
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Discard this bill?"),
            body: _t("The current lines have not been saved and will be lost."),
            confirmLabel: _t("Discard"),
            confirm: () => this.resetOrder(),
            cancel: () => {},
        });
    }

    openOrders() {
        this.action.doAction("velkio_easy_pos_with_whatsapp_integration.action_pos_screen_order");
    }

    openCurrentOrder() {
        if (!this.state.orderId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: MODEL,
            res_id: this.state.orderId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("velkio_easy_pos_with_whatsapp_integration.screen", PosScreen);
