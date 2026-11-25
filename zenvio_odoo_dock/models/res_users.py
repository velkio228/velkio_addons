from odoo import fields, models

DOCK_POSITIONS = [
    ("left", "Left"),
    ("right", "Right"),
    ("top", "Top"),
    ("bottom", "Bottom"),
]

DOCK_STYLES = [
    ("dark", "Dark"),
    ("floating", "Floating"),
    ("glass", "Glass"),
    ("light", "Light"),
    ("odoo", "Odoo Purple"),
    ("accent", "Accent Colour"),
]

DOCK_ICON_SIZES = [
    ("small", "Small"),
    ("medium", "Medium"),
    ("large", "Large"),
]

DOCK_OVERVIEW_THEMES = [
    ("auto", "Follow Odoo (light / dark mode)"),
    ("dark", "Dark"),
    ("light", "Light"),
]


class ResUsers(models.Model):
    _inherit = "res.users"

    zenvio_dock_configured = fields.Boolean(
        string="Zenvio Dock Configured",
        help="Technical: True once the user has saved their own dock apps.",
    )
    zenvio_dock_position = fields.Selection(DOCK_POSITIONS, string="Dock Position", default="left")
    zenvio_dock_style = fields.Selection(DOCK_STYLES, string="Dock Style", default="dark")
    zenvio_dock_icon_size = fields.Selection(DOCK_ICON_SIZES, string="Dock Icon Size", default="medium")
    zenvio_dock_autohide = fields.Boolean(string="Auto-hide Dock")
    zenvio_dock_show_recent = fields.Boolean(string="Show Recent Apps in Dock", default=True)
    zenvio_dock_recent_limit = fields.Integer(string="Recent Apps in Dock", default=5)
    zenvio_dock_accent_color = fields.Char(string="Dock Accent Colour", default="#E95420")
    zenvio_dock_magnify = fields.Boolean(string="Magnify Dock Icons on Hover")
    zenvio_dock_shortcuts = fields.Boolean(string="Dock Keyboard Shortcuts", default=True)
    zenvio_dock_show_badges = fields.Boolean(string="Dock Notification Badges", default=True)
    zenvio_dock_show_favorites = fields.Boolean(string="Show Favourite Menus in Dock", default=True)
    zenvio_dock_overview_theme = fields.Selection(
        DOCK_OVERVIEW_THEMES, string="Dock Overview Theme", default="auto"
    )
    zenvio_dock_recent_ids = fields.Char(
        string="Recent Apps (technical)",
        help="Comma separated ir.ui.menu ids, most recent first.",
    )
    zenvio_dock_fav_menu_ids = fields.Char(
        string="Favourite Menus (technical)",
        help="Comma separated ir.ui.menu ids, in dock order.",
    )
    zenvio_dock_recent_records = fields.Text(
        string="Recent Records (technical)",
        help="JSON list of recently opened records, most recent first.",
    )
