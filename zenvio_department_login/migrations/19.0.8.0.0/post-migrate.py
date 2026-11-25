from odoo import SUPERUSER_ID, api


def _columns(cr, table):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
    return {row[0] for row in cr.fetchall()}


def _ids(cr, table, line_id, column):
    cr.execute("SELECT to_regclass(%s)", [table])
    if not cr.fetchone()[0]:
        return []
    cr.execute(f'SELECT "{column}" FROM "{table}" WHERE line_id = %s', [line_id])
    return [row[0] for row in cr.fetchall()]


def migrate(cr, version):
    """Model rules used to hold everything; the Access Rights screen now has
    one list per tab. Move record filters, buttons/tabs, fields and chatter
    of each old rule into the Domain, Button/Tab, Field and Chatter lists."""
    cols = _columns(cr, 'zenvio_access_profile_model')
    if 'domain' not in cols:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT id, profile_id, model_id, domain, state_field_id, hide_chatter FROM zenvio_access_profile_model")
    for line_id, profile_id, model_id, domain, state_field_id, hide_chatter in cr.fetchall():
        base = {'profile_id': profile_id, 'model_id': model_id}
        state = {'state_field_id': state_field_id,
                 'state_value_ids': [(6, 0, _ids(cr, 'zenvio_access_profile_model_state_rel', line_id, 'value_id'))]}
        if domain and domain.strip() not in ('', '[]'):
            env['zenvio.access.profile.domain'].create(dict(base, domain=domain))
        buttons = _ids(cr, 'zenvio_access_profile_model_button_rel', line_id, 'node_id')
        pages = _ids(cr, 'zenvio_access_profile_model_page_rel', line_id, 'node_id')
        if buttons or pages:
            env['zenvio.access.profile.button'].create(dict(base, **state, hide_button_ids=[(6, 0, buttons)],
                                                            hide_page_ids=[(6, 0, pages)]))
        hidden = _ids(cr, 'zenvio_access_profile_model_hide_field_rel', line_id, 'field_id')
        locked = _ids(cr, 'zenvio_access_profile_model_ro_field_rel', line_id, 'field_id')
        if hidden:
            env['zenvio.access.profile.field'].create(dict(base, **state, field_ids=[(6, 0, hidden)], invisible=True))
        if locked:
            env['zenvio.access.profile.field'].create(dict(base, **state, field_ids=[(6, 0, locked)], readonly=True))
        if hide_chatter:
            env['zenvio.access.profile.chatter'].create(dict(base, hide_chatter=True))
