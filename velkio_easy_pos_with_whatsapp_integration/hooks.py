from odoo import _
from odoo.exceptions import UserError


def pre_init_hook(env):
    env.cr.execute("SELECT name FROM ir_module_module WHERE name IN ('pos_screen', 'pos_screen_whatsapp') AND state IN ('installed', 'to upgrade', 'to remove')")
    legacy = [row[0] for row in env.cr.fetchall()]
    if legacy:
        raise UserError(_("Existing POS modules (%s) require a database migration to the merged Velkio module. Keep their bills and settings; follow MIGRATION.md before installing the new name.", ', '.join(legacy)))
