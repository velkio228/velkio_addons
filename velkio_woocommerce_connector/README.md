# WooCommerce Connector

By Velkio Odoo Solutions. Version 19.0.1.0.1. License: OPL-1.

Bring WooCommerce products, customers and sales orders into Odoo. Update mapped store products from Odoo, manage multiple connections and review your synchronization activity in one workspace.

## Requirements

Odoo 19 on Odoo.sh or on-premise, with custom Python add-ons enabled. Standard Odoo Online does not support these modules.

- An Odoo 19 environment with Sales and Inventory. Required Odoo dependencies are installed with the module.
- A WooCommerce store reachable from the Odoo server, preferably over HTTPS.
- A WooCommerce REST API key with Read/Write access, associated with a user allowed to access the required store data.
- WordPress permalinks set to an option other than Plain. WooCommerce uses the wc/v3 REST API for this connector.

## Setup

1. **Install the connector.** Add the module to your custom add-ons, update the Apps list and install WooCommerce Connector. Open WooCommerce from the app menu.

2. **Create your store API keys.** In WordPress, go to WooCommerce → Settings → Advanced → REST API → Add Key. Choose Read/Write permission and generate the key. Save the Consumer Key and Consumer Secret securely.

3. **Add an Odoo connection.** Open WooCommerce → Instances → New. Enter a name, Store URL, Consumer Key and Consumer Secret. Select the company, warehouse and pricelist. Leave automatic order confirmation off while checking your first import.

4. **Test the connection.** Save the instance and select Test Connection. If it fails, check the store URL, API permissions and whether the Odoo server can reach the store.

5. **Import your first records.** Select Import Products, then Import Customers, then Import Orders. Review the new Odoo records and their mappings. Sync All runs these three imports together.

6. **Export and review.** Check Product Mappings before selecting Export Products. Open Sync Logs to review completed actions and the dashboard for activity across stores.

## Scope

Synchronization is action-based. Sync All imports products, customers and orders; product export is a separate action. This release does not provide scheduled sync, webhooks, stock-quantity sync, image sync, variation sync, refund sync or order-status updates back to WooCommerce. Shipping charges, discounts and tax-line mapping are not included in the order import.

## Frequently asked questions

**Does it synchronize automatically?**

No. This release uses manual actions in Odoo. Sync All runs product, customer and order imports; it does not export products.

**Can I connect more than one store?**

Yes. Create a separate instance for each store, with its own credentials and Odoo defaults.

**Can I export every Odoo product?**

Exports use the selected instance’s Product Mappings. Review or create the mappings for the products you intend to export.

**Will repeat imports duplicate orders?**

Orders already linked by a mapping for that instance are skipped. This also means later changes to an already imported order are not re-applied.

**Is there an import size limit?**

Each action reads up to 10 pages of 100 records per resource. Catalogs or order histories above 1,000 records need an extended import strategy; this release does not include a historical migration tool.

**What data leaves Odoo?**

Export Products sends mapped product names, SKUs and prices to your configured WooCommerce store. Imports retrieve store products, customers and orders. Connections use the credentials you configure.

## Support

velkio.odoosolution@gmail.com

The marketplace presentation is in `static/description/index.html`.
