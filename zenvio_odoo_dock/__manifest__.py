{
    "name": "Zenvio Odoo Dock",
    "summary": "App dock for the Odoo backend: pinned and recent apps, favourite menus, badges, any screen side",
    "description": """
Zenvio Odoo Dock
================
Adds an app dock to the Odoo backend, on the left, right, top or bottom of the
screen.

* Pin the apps you want (+ button, or pin from the overview)
* Recently opened apps appear after a separator, with "running" dots
* Styles: Dark, Floating, Glass, Light, Odoo Purple, Accent Colour
* Icon size, accent colour, auto-hide and optional magnify on hover
* Drag & drop to reorder; drag a recent app onto the dock to pin it
* Right-click menu: open, open in new tab, move, pin/unpin, remove from recent
* "Show Applications" opens a full-screen overview with search (apps, menus
  and recent records), recent apps, favourite menus and all apps
* Notification badges (unread Discuss messages, due To-dos and activities)
* Favourite menus pinned next to apps
* Keyboard shortcuts: Alt+Shift+O (overview), Alt+Shift+1..9 (pinned apps)
* Middle-click / Ctrl+click opens apps in a new tab
* Overview follows Odoo light / dark mode
* Everything is saved in the database, per user
""",
    "version": "19.0.1.1.10",
    "images": ["static/description/banner.png"],
    "category": "Productivity",
    "author": "Zenvio",
    "website": "https://zenvio.com",
    "license": "LGPL-3",
    "price": 19.0,
    "currency": "USD",
    "depends": ["web"],
    "data": [
        "security/ir.model.access.csv",
        "security/zenvio_dock_security.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zenvio_odoo_dock/static/src/dock/zenvio_dock.scss",
            "zenvio_odoo_dock/static/src/dock/zenvio_dock.xml",
            "zenvio_odoo_dock/static/src/dock/zenvio_dock.js",
            "zenvio_odoo_dock/static/src/dock/record_tracker.js",
        ],
    },
    "installable": True,
    "application": False,
}
