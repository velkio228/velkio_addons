def migrate(cr, version):
    """Departments no longer have their own Odoo user: archive the ones
    earlier versions created, so only real people stay in the Users list."""
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'zenvio_department_access' AND column_name = 'user_id'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE res_users SET active = FALSE
         WHERE id IN (SELECT user_id FROM zenvio_department_access WHERE user_id IS NOT NULL)
    """)
    cr.execute("ALTER TABLE zenvio_department_access ALTER COLUMN user_id DROP NOT NULL")
