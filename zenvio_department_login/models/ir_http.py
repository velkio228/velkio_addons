import logging

from odoo import api, models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate_explicit(cls, auth):
        """End an employee session as soon as the employee, the department
        or its Top Management user changes, instead of letting it run with that user's full rights.

        Done like Odoo's own session check: log out *before* authenticating,
        so the route's auth method sends the browser to the login page once
        (raising here instead left the session unsaved and looped)."""
        line_id = request.session.get('zenvio_dept_line_id')
        if line_id and request.session.uid is not None:
            line = request.env(su=True)['zenvio.department.employee'].browse(line_id).exists()
            if not (line and line.active and line.access_id.active and line.employee_id.active
                    and line.access_id.owner_id.id == request.session.uid
                    and not line._zenvio_login_disabled()):
                _logger.info("Department login %s no longer valid, logging out", line_id)
                request.session.logout(keep_db=True)
                # Keep the session id: the login page rendered by this same
                # request carries a CSRF token made from it (a new id made
                # that form fail with "Session expired"). Logging in again
                # rotates the id anyway.
                request.session.should_rotate = False
                request.env = api.Environment(request.env.cr, None, request.session.context)
        super()._authenticate_explicit(auth)

    @classmethod
    def _handle_debug(cls):
        super()._handle_debug()
        # "Disable Developer Mode": no ?debug=1 for these employees.
        if request.session.get('zenvio_dept_line_id') and request.session.debug:
            line = request.env(su=True)['zenvio.department.employee'].browse(request.session['zenvio_dept_line_id']).exists()
            profile = line and line._zenvio_profile()
            if profile and profile.disable_debug:
                request.session.debug = ''

    def session_info(self):
        info = super().session_info()
        session = self.env['zenvio.department.employee']._zenvio_session()
        if session and session['rules']['hide_spreadsheet']:
            info['can_insert_in_spreadsheet'] = False
        if session:
            # The browser caches views and actions by request, and every request
            # carries the user context: this key keeps each employee (and each
            # version of their access) apart from the Top Management user and
            # from each other. Changing registry_hash instead made Odoo delete
            # the shared browser database under other open tabs.
            rules = session['rules']
            info.setdefault('user_context', {})['zenvio_access'] = \
                f"{session['line_id']}-{rules['id']}-{rules['version']}"

        line = self.env['zenvio.department.employee']._get_session_line()
        if line:
            info['zenvio_department'] = {
                'department': line.access_id.name,
                'employee': line.employee_id.name,
                'role': dict(line._fields['role']._description_selection(self.env))[line.role],
                'login_code': line.login_code,
                'icon': line.access_id.icon or 'fa-building',
                'color': line.access_id.color or 0,
                # read by department_systray.js: other modules may switch it back on server side
                'hide_spreadsheet': bool(session and session['rules']['hide_spreadsheet']),
                'access_key': info.get('user_context', {}).get('zenvio_access', ''),
                'switched_from': (
                    self.env['res.users'].sudo().browse(request.session.get('zenvio_switch_origin') or 0).exists().name
                    or self.env['zenvio.department.employee'].sudo().browse(
                        request.session.get('zenvio_switch_origin_line') or 0).exists().employee_id.name
                    or False),
            }
        # The top bar's employee switcher: administrators, Top Management users,
        # and their sessions already switched into an employee.
        if request and request.session.uid and (
                request.session.get('zenvio_switch_origin') or (
                    not request.session.get('zenvio_dept_line_id')
                    and (self.env.user.has_group('base.group_system')
                         or self.env.user.has_group('zenvio_department_login.group_department_manager')))):
            info['zenvio_can_switch'] = True
        elif request and request.session.get('zenvio_dept_line_id'):
            # an employee with Can Switch (or working as a colleague they opened)
            Line = self.env['zenvio.department.employee']
            if request.session.get('zenvio_switch_origin_line') or Line._zenvio_switch_origin_line()._zenvio_switch_peers():
                info['zenvio_can_switch'] = True
        return info
