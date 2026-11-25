from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Each department now edits a User and a Manager access of its own."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['zenvio.department.access'].with_context(active_test=False).search([])._ensure_role_profiles()
