def migrate(cr, version):
    """Department logins are shown in Settings → Users again: undo the filter
    that 19.0.5.0 put on the Users action."""
    cr.execute("""
        UPDATE ir_act_window SET domain = NULL
         WHERE id = (SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'action_res_users')
    """)
