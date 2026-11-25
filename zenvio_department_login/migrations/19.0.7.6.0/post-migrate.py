def migrate(cr, version):
    """Give departments created before the card view a color of their own."""
    cr.execute("UPDATE zenvio_department_access SET color = id % 11 + 1 WHERE COALESCE(color, 0) = 0")
