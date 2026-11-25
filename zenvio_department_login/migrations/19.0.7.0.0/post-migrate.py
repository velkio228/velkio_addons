def migrate(cr, version):
    """Employees now log in as their CEO: archive the hidden User / Manager
    logins that 19.0.5.x created for each department."""
    cr.execute("UPDATE res_users SET active = FALSE WHERE zenvio_department_login IS TRUE")
