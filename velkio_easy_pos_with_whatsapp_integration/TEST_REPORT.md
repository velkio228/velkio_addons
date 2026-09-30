# Validation report — 30 September 2026

Merged module: `velkio_easy_pos_with_whatsapp_integration`, version 17.0.1.0.0.

## Verified results

Fresh installation on a disposable Odoo 17 database using Community core and Enterprise WhatsApp addons completed successfully. The post-install suite passed **25 tests, 0 failures, 0 errors**. Python/XML parsing and manifest data/asset paths passed.

Cashier, separate cashier, manager and settings-administrator scenarios cover bill/line ownership, counter assignment, configuration permissions, company boundaries, draft/confirmed payment, cancellation/reset, paid financial immutability and repeated payment. Functional scenarios cover product/customer lookup, exact normalized phone matching, taxes/discounts, receipt rendering, duplicate-product stock demand, delivery, UI save/load, manual WhatsApp-number persistence and invalid input.

WhatsApp integration tests create actual composer/message records with network sending mocked. They cover queue creation, simulated sent/error callbacks, stale callback protection, repeated-payment notification suppression and failed sending/template access preserving successful payment.

## Browser checks

- Cashier billing screen loads
- Product/customer search and draft save
- Parked bill reload preserves WhatsApp override
- Payment persists bill and receipt number
- Actual PDF receipt generated (28597 bytes)
- Paid receipt opens WhatsApp composer
- Manager counter configuration loads

No application page errors or console errors were recorded in the successful cashier browser run. Chromium rendered the branded screen; its screenshot is `static/description/billing_screen.png`. A real PDF receipt was generated and checked for its PDF signature. The payment record includes its delivery; backend tests additionally verify done state and stock quantities.

## Corrections included

- Correct merged module asset paths and namespace references.
- Enforce allowed workflow transitions and immutable confirmed/paid financial data.
- Lock repeated payment requests to prevent duplicate delivery/notification.
- Check cashier ownership, assigned counters, allowed companies and configuration permissions.
- Aggregate duplicate stock lines and validate quantity/UoM/discount inputs.
- Preserve manual receipt number when reopening a parked draft.
- Isolate automatic WhatsApp errors from payment and retain immediate sending failures.
- Ignore stale message callbacks and require full phone equality during customer lookup.
- Enable payment for confirmed bills without accepting financial edits.
- Improve optional receipt-number label contrast.

## Practical limits

Live Meta delivery to a recipient was not tested: no production WhatsApp credentials or approved template were supplied. Physical printers, payment terminals, actual gateway charging and accounting reconciliation were not tested. Payment methods record the selected method; this standalone billing app does not charge a gateway or create an accounting payment/invoice. Lot/serial tracked products need a separate selection flow and are rejected for automatic delivery. Returns use a separate return workflow.

This is a fresh-install package. Existing installed `pos_screen`/`pos_screen_whatsapp` databases need an ownership/XML-ID migration; the installation hook deliberately rejects that combination. See MIGRATION.md. Source modules were preserved. No production database was modified.

The browser fixture initially lacked a sender email, which blocked a stock notification; it was configured before the successful run. Normal Odoo company/user email and notification settings remain required.

## Repeat backend validation

On an isolated database with Enterprise WhatsApp addons available:

```sh
odoo-bin -d TEST_DATABASE -i velkio_easy_pos_with_whatsapp_integration --test-enable --test-tags /velkio_easy_pos_with_whatsapp_integration --stop-after-init --without-demo=all
```

Use a disposable database and disable cron/external messaging for automated checks. Integration tests mock Meta network sending.
