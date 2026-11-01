"""Build the script-free Odoo Apps page for Velkio WooCommerce Connector Pro.

Usage: python3 tools/build_pro_presentation.py
Reuses the helpers and inline layout from build_app_presentation.py.
"""
from html import escape
from pathlib import Path
from build_app_presentation import ROOT, section, heading, para, cards, button, callout
from inline_store_layout import inline_layout

OUT = ROOT / 'velkio_woocommerce_connector_pro' / 'static' / 'description'
EMAIL = 'velkio.odoosolution@gmail.com'
FEATURES = [
    ('Scheduled incremental sync', 'A scheduled action runs every 5 minutes and imports only records modified since the last run. Each store has its own interval, with a minimum of 5 minutes.'),
    ('Real-time webhooks', 'Order, product and customer created/updated events are accepted from WooCommerce and verified with HMAC-SHA256. Webhooks require an https web.base.url.'),
    ('Stock push from Odoo', 'Sends free quantity per warehouse to mapped WooCommerce products, in batches, and only when the quantity changed.'),
    ('Variations and main image', 'Variations are matched by attribute. A per-variant price is applied only when a single attribute varies. The main product image is imported.'),
    ('Shipping, fees and notes', 'Shipping and fee lines become order lines. Coupons, payment method and the customer note are added to the order chatter.'),
    ('Tax handling', 'Choose Odoo taxes, no taxes, or mapped taxes, and use the Import Tax Rates action to build the mapping.'),
    ('Delivery addresses', 'The WooCommerce shipping address is created as a child contact of the customer.'),
    ('Order status updates', 'Confirming an order sets it to processing, a fully delivered order to completed, and a cancelled order to cancelled in WooCommerce. A WooCommerce cancel, refund or failed status cancels the Odoo order.'),
    ('Order status filter', 'Choose which WooCommerce statuses are imported. The default is processing, on-hold and completed.'),
]
STEPS = [
    ('Install the base connector', 'Install Velkio WooCommerce Connector first and connect your store with WooCommerce REST API keys.'),
    ('Install Connector Pro', 'Install this module. It adds its options to your existing store connections.'),
    ('Choose what to sync', 'Open the store connection and select products, customers, orders and stock push.'),
    ('Map taxes', 'Pick the tax mode and, for mapped taxes, run Import Tax Rates and map each rate to an Odoo tax.'),
    ('Enable automation', 'Turn on Automatic Sync and set the interval. For webhooks, make sure web.base.url is an https address and copy the webhook address into WooCommerce.'),
    ('Check the first run', 'Run a small sync, then review the sync log and the created orders.'),
]
NOT_INCLUDED = [
    ('Refund credit notes', 'Refunds in WooCommerce cancel the Odoo order but do not create credit notes.'),
    ('Image export', 'Only the main product image is imported. Images are not sent to WooCommerce.'),
    ('Multi-attribute variant pricing', 'Per-variant prices are applied only when exactly one attribute varies.'),
]
FAQS = [
    ('Does this work without the base connector?', 'No. Velkio WooCommerce Connector and Odoo Sales and Inventory (sale_stock) are required dependencies.'),
    ('Which Odoo version is supported?', 'Odoo 19.0, Community and Enterprise.'),
    ('How often does automatic sync run?', 'A scheduled action runs every 5 minutes. Each store has its own interval, with a minimum of 5 minutes.'),
    ('Do webhooks need anything special?', 'Yes. Your Odoo web.base.url must be an https address that WooCommerce can reach.'),
]
REQS = ['Odoo 19.0 with Sales and Inventory', 'Velkio WooCommerce Connector installed', 'A WooCommerce store with REST API credentials', 'A public https Odoo URL if you use webhooks']


def build():
    c = ['<section class="oe_container" style="font-family:Arial,Helvetica,sans-serif;color:#282532;background-color:#FFFFFF;">', '<div class="container py-3">']
    c.append('<div class="row align-items-center mb-3"><div class="col-sm-4"><img src="velkio_logo.png" alt="Velkio Odoo Solutions logo" width="165" class="img-fluid"/></div><div class="col-sm-8 text-sm-right text-sm-end"><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Odoo 19</span><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Community &amp; Enterprise</span></div></div>')
    hero = '<div class="text-center mb-4"><p style="font-size:12px;letter-spacing:2px;color:#9A7135;font-weight:700;">VELKIO ODOO SOLUTIONS</p><h1 style="font-size:42px;line-height:1.15;font-weight:800;color:#282532;">Velkio WooCommerce Connector Pro</h1><p style="font-size:20px;line-height:1.5;color:#714B67;">Automatic sync for stock, variations, orders, shipping and taxes</p></div>'
    hero += para('Connector Pro extends Velkio WooCommerce Connector with scheduled sync, webhooks, stock push, variations, shipping and fee lines, tax mapping and order status updates.')
    hero += '<ul style="color:#514A59;font-size:16px;line-height:1.9;">' + ''.join('<li>' + escape(r) + '</li>' for r in REQS) + '</ul>'
    hero += '<div class="text-center">' + button('Explore capabilities', '#features') + button('Setup', '#setup', True) + '</div>'
    c.append(section('overview', hero, True))
    c.append('<div class="my-4"><img src="banner.png" alt="Velkio WooCommerce Connector Pro: scheduled sync, stock push, variants, order status, shipping and taxes" class="img-fluid w-100 rounded"/></div>')
    c.append(section('features', heading('Capabilities', 'What Connector Pro adds') + cards(FEATURES)))
    c.append(callout('Start with the base connector', 'Connector Pro adds options to your existing store connections, so connect your store first.'))
    c.append(section('setup', heading('Getting started', 'Six steps to automatic sync') + cards(STEPS, 'col-md-6'), True))
    c.append(section('scope', heading('Scope', 'What is not included') + cards(NOT_INCLUDED), True))
    c.append(section('faq', heading('Questions', 'Check before you install') + cards(FAQS, 'col-md-6')))
    support = heading('Velkio support', 'Get help') + para('Include your Odoo and module versions. Remove passwords and API keys from shared screenshots.')
    support += callout('Need help?', 'Email us with the action, the exact error and the relevant log lines.', 'mailto:' + EMAIL, 'Email Velkio support')
    support += para(EMAIL) + para('Independent integration by Velkio Odoo Solutions. WooCommerce is a trademark of its owners.', 'small')
    c.append(section('support', support))
    c.extend(['</div>', '</section>'])
    (OUT / 'index.html').write_text(inline_layout('\n'.join(c) + '\n'), encoding='utf-8')


if __name__ == '__main__':
    build()
