# Zenvio WooCommerce Connector Pro (Odoo 19)

Paid extension for `zenvio_woocommerce_connector` (OPL-1, USD 79).

## Features
- **Automatic sync** – cron every 5 minutes runs each store at its own interval; products and orders are read incrementally with `modified_after`.
- **Webhooks** – one click registers order/product/customer webhooks; payloads are verified with HMAC-SHA256. Requires a public `https://` `web.base.url`.
- **Stock push** – free quantity per warehouse, sent in batches of 100, only when it changed.
- **Variations & images** – variable products become Odoo attributes/variants; main image is imported.
- **Orders** – status filter, shipping and fee lines, delivery addresses, coupons/notes in chatter, tax modes (Odoo / none / mapped rates).
- **Order status both ways** – confirm → processing, fully delivered → completed, cancel → cancelled; WooCommerce cancel/refund/failure cancels the Odoo order.

## Limits
Per-variant prices are exact only when a single attribute varies. Images are imported, not exported. Refunds don't create credit notes.
