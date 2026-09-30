# Velkio Easy POS with WhatsApp Integration

Technical name: `velkio_easy_pos_with_whatsapp_integration`  
Version: 17.0.1.0.0 · Odoo 17 Enterprise · LGPL-3

A single app combining the original `pos_screen` billing counter and
`pos_screen_whatsapp` receipt integration. Orders remain in `pos.screen.order`;
this is a standalone counter app and does not depend on Odoo Point of Sale.

## Features

- Type-ahead product search, configurable result columns, customer lookup and
  phone-number customers.
- Pricelists, discounts, taxes and parked draft bills.
- Counter-specific payment methods and machine names.
- Immediate stock delivery for untracked storable products when configured.
- Browser receipts at 58 mm, 80 mm or A4; a PDF bill report for WhatsApp.
- Automatic receipt queueing after payment and a manual Send Receipt action.
- Receipt-number override, queue state, delivery callback and failure tracking.
- Cashier ownership of bills and lines, manager access, company filtering and
  immutable paid/confirmed financial details.

Payment methods record the tender choice. This app does not charge cards,
initiate UPI transactions or create accounting payments/invoices. Negative
quantities/refunds are not supported; process inventory returns separately.
Automatic counter deliveries support untracked storable products; tracked
products require an inventory flow with lot/serial selection. Cashiers inherit
Inventory User access because the counter reads stock and validates deliveries.

## Installation and setup

1. For a fresh Odoo 17 Enterprise database, add this folder to your addons path.
   Dependencies include `base`, `web`, `mail`, `product`, `stock`, `account` and
   Enterprise `whatsapp`. Update Apps and install the app.
2. Assign Velkio Easy POS / Cashier or Manager. Managers configure counters,
   search columns, payment methods and receipt settings.
3. The Main Counter starts with delivery disabled. Configure its outgoing
   operation type and stock/customer locations before enabling delivery.
4. Set allowed cashiers, pricelist, payment methods and receipt size/header/footer.
5. Configure a WhatsApp Business account in Odoo. Set the bill document template
   account, confirm the PDF report and submit the template to Meta for approval.
6. Select the template on the counter and enable Send Bill on WhatsApp if needed.
   Give cashiers access to that template through Odoo WhatsApp allowed users.
7. Open Billing Screen, choose a customer or number, add products, select a
   payment method and pay. A failed WhatsApp send records the error while
   retaining the payment. Repeated payment calls do not resend the receipt.

The provided template begins as a draft and cannot deliver live messages until
approved and connected to a WhatsApp Business account. The configured Odoo queue
and webhook process actual delivery. Live Meta delivery requires your account
credentials and approved template and was not sent during the offline tests.

## Existing installations

See MIGRATION.md before using this module on a database that already has either
original module installed. Original folders are preserved. A rename is not an
uninstall/reinstall operation; that can remove bills and related settings.

## Tests

The `tests/` directory contains Odoo integration tests. Run with your Odoo 17
Enterprise addons and `--test-tags /velkio_easy_pos_with_whatsapp_integration`
on a disposable database. See TEST_REPORT.md for this build's observed results.

## Publisher and support

Velkio – Odoo Solutions · https://velkio.com  
Support: velkio.odoosolution@gmail.com
