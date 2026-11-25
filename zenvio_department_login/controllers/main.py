import logging
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request

from odoo.addons.web.controllers.dataset import DataSet
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db

_logger = logging.getLogger(__name__)

# Wrong passwords allowed per employee code before it is locked for a while.
MAX_FAILURES = 5
COOLDOWN = timedelta(minutes=1)


def _find_line(login_code):
    """Usable mapped employee for a login code, if any."""
    return request.env['zenvio.department.employee'].sudo().search([
        ('login_code', '=', login_code), ('access_id.active', '=', True), ('employee_id.active', '=', True),
    ], limit=1)


def _cooling_down(login_code):
    since = fields.Datetime.now() - COOLDOWN
    return request.env['zenvio.department.login.log'].sudo().search_count([
        ('login_code', '=', login_code), ('result', '=', 'failed'), ('login_date', '>=', since),
    ]) >= MAX_FAILURES


def _department_login(line, login_code, password, redirect=None):
    """Log the employee in as the Top Management user of their department.

    Returns ``(response, None)`` on success, ``(None, error message)`` otherwise.
    The employee's password is checked here first: Odoo counts failed logins
    per user, so a wrong employee password must never reach the shared user
    (it would lock out the Top Management user and every other employee).
    """
    if not line or not line.active:
        _log(line, login_code, 'failed')
        return None, _("Wrong employee code or password.")
    # The lock comes first: no password may be checked while the code is locked,
    # or the "disabled" message below would confirm a correct guess.
    if _cooling_down(login_code):
        return None, _("Too many failed attempts for this employee code. Please wait a minute and try again.")
    if line._zenvio_login_disabled() and line._verify_password(password or ''):
        _log(line, login_code, 'failed')
        return None, _("Login is disabled for your access. Please contact your manager.")
    if not line._verify_password(password or ''):
        _log(line, login_code, 'failed')
        return None, _("Wrong employee code or password.")
    try:
        credential = {
            'type': 'department_password',
            'login': line.access_id.owner_id.login,
            'line_id': line.id,
            'password': password or '',
        }
        auth_info = request.session.authenticate(request.env, credential)
    except AccessDenied as e:
        _log(line, login_code, 'failed')
        # e.g. the Top Management user itself is locked or archived
        return None, str(e.args[0]) if e.args and e.args[0] != 'Access Denied' else _("Wrong employee code or password.")
    for key in ('zenvio_switch_origin', 'zenvio_switch_origin_line'):
        request.session.pop(key, None)
    request.session['zenvio_dept_line_id'] = line.id
    line.last_login = fields.Datetime.now()
    _log(line, login_code, 'success')
    return request.redirect(Home()._login_redirect(auth_info['uid'], redirect=redirect)), None


def _log(line, login_code, result, switched_by=None, switched_by_employee=None):
    try:
        request.env['zenvio.department.login.log'].sudo().create({
            'switched_by_id': switched_by.id if switched_by else False,
            'switched_by_employee_id': switched_by_employee.id if switched_by_employee else False,
            'access_id': line.access_id.id if line else False,
            'employee_id': line.employee_id.id if line else False,
            'login_code': login_code,
            'ip_address': request.httprequest.remote_addr,
            'user_agent': (request.httprequest.user_agent.string or '')[:255],
            'result': result,
        })
    except Exception:
        _logger.exception("Could not write the department login log")


class ZenvioHome(Home):

    @http.route()
    def web_login(self, redirect=None, **kw):
        """Let employees use their login code on the normal login page too."""
        if request.httprequest.method == 'POST' and not (kw.get('login') or '').strip():
            # Odoo fails with a server error (KeyError) on an empty login:
            # answer like any other wrong login instead.
            request.params['login'] = kw['login'] = ' '
        if request.httprequest.method == 'POST' and kw.get('login'):
            ensure_db()
            # A normal login must never keep a previous employee's or switch marks.
            for key in ('zenvio_dept_line_id', 'zenvio_switch_origin', 'zenvio_switch_origin_line'):
                request.session.pop(key, None)
            typed = kw['login'].strip()
            login_code = typed.upper()
            line = _find_line(login_code)
            is_real_login = request.env['res.users'].sudo().with_context(active_test=False).search_count(
                [('login', '=', typed)], limit=1)
            if line and not is_real_login:
                response, error = _department_login(line, login_code, kw.get('password'), redirect=redirect)
                if response:
                    return response
                # Show our message (e.g. the lock) instead of Odoo's generic one.
                response = super().web_login(redirect=redirect, **kw)
                if getattr(response, 'qcontext', None) is not None:
                    response.qcontext['error'] = error
                return response
        return super().web_login(redirect=redirect, **kw)


class ZenvioDataSet(DataSet):
    """Refuse the buttons an employee's access profile hides, even when
    they are called directly instead of through the screen."""

    @http.route()
    def call_kw(self, model, method, args, kwargs, path=None):
        _check_button(model, method, args)
        return super().call_kw(model, method, args, kwargs, path=path)

    @http.route()
    def call_button(self, model, method, args, kwargs, path=None):
        _check_button(model, method, args)
        return super().call_button(model, method, args, kwargs, path=path)


def _check_button(model, method, args):
    if model == 'base_import.import' and method in ('execute_import', 'parse_preview') \
            and request.session.get('zenvio_dept_line_id'):
        # "Hide Import": refuse the import itself, not only the button.
        wizard = request.env[model].sudo().browse([i for i in (args[0] if args and isinstance(args[0], list) else [])
                                                  if isinstance(i, int)]).exists()
        session = request.env['zenvio.department.employee']._zenvio_session()
        for target in set(wizard.mapped('res_model')):
            rule = session and session['rules']['models'].get(target) or {}
            if session and (session['rules']['hide_import'] or rule.get('hide_import')):
                raise AccessError(_("You are not allowed to import records here."))
    if model in request.env and request.session.get('zenvio_dept_line_id'):
        ids = args[0] if args and isinstance(args[0], list) else []
        request.env[model]._zenvio_check_button(method, [i for i in ids if isinstance(i, int)])


def _switch_origin():
    """User allowed to switch: the administrator / Top Management user behind
    this session (also while already switched into an employee), else None."""
    session = request.session
    if session.get('zenvio_dept_line_id') and not session.get('zenvio_switch_origin'):
        return None  # employee sessions switch through _switch_origin_line()
    user = request.env['res.users'].sudo().browse(session.get('zenvio_switch_origin') or session.uid).exists()
    if not user or not user.active or user.share:
        return None
    if user.has_group('base.group_system') or user.has_group('zenvio_department_login.group_department_manager'):
        return user
    return None


def _switch_origin_line():
    return request.env['zenvio.department.employee']._zenvio_switch_origin_line()


def _switch_lines(origin):
    """Employee mappings ``origin`` (administrator / Top Management) may switch into."""
    domain = [('active', '=', True), ('access_id.active', '=', True), ('employee_id.active', '=', True)]
    if not origin.has_group('base.group_system'):
        domain.append(('access_id.owner_id', '=', origin.id))
    return request.env['zenvio.department.employee'].sudo().search(domain, order='department_id, role desc, employee_id')


def _become(user):
    """Turn this session into ``user``'s, the way Odoo finalizes a login."""
    request.session['pre_login'] = user.login
    request.session['pre_uid'] = user.id
    request.session.finalize(request.env)
    request.update_env(user=user.id)


class ZenvioDepartmentSwitch(http.Controller):
    """Switch (top bar): an administrator (any department) or a Top Management
    user (own departments) opens Odoo as a mapped employee without their
    password; an employee with Can Switch opens the employees of their
    Switch Departments."""

    @http.route('/web/department/switch/targets', type='jsonrpc', auth='user')
    def switch_targets(self):
        origin = _switch_origin()
        lines = _switch_lines(origin) if origin else _switch_origin_line()._zenvio_switch_peers()
        if not origin and request.session.get('zenvio_switch_origin_line'):
            lines |= _switch_origin_line()  # while working as a colleague: the employee themselves, to come back
        current = request.session.get('zenvio_dept_line_id')
        departments = {}
        for line in lines.sorted(lambda l: (l.department_id.name or '', l.role != 'manager', l.employee_id.name or '')):
            access = line.access_id
            dept = departments.setdefault(access.id, {
                'id': access.id, 'name': access.name, 'icon': access.icon or 'fa-building',
                'color': access.color or 0, 'owner': access.owner_id.name, 'employees': [],
            })
            dept['employees'].append({
                'line_id': line.id, 'name': line.employee_id.name, 'code': line.login_code,
                'role': dict(line._fields['role']._description_selection(request.env))[line.role],
                'login_disabled': line._zenvio_login_disabled(), 'current': line.id == current,
            })
        return list(departments.values())

    @http.route('/web/department/switch/<int:line_id>', type='jsonrpc', auth='user')
    def switch_to(self, line_id):
        origin = _switch_origin()
        if origin:
            line = _switch_lines(origin).filtered(lambda l: l.id == line_id)
        else:
            me = _switch_origin_line()
            line = (me | me._zenvio_switch_peers()).filtered(lambda l: l.id == line_id) if me else None
        if not line:
            raise AccessError(_("You cannot open this employee's session."))
        if line._zenvio_login_disabled():
            raise AccessError(_("Login is disabled for %s's access.", line.employee_id.name))
        if origin:
            _become(line.access_id.owner_id)
            request.session['zenvio_switch_origin'] = origin.id
            _log(line, line.login_code, 'switch', switched_by=origin)
        else:
            # Same Top Management user (Switch Departments never cross it): only the employee changes.
            if line == me:
                request.session.pop('zenvio_switch_origin_line', None)
            else:
                request.session['zenvio_switch_origin_line'] = me.id
                _log(line, line.login_code, 'switch', switched_by_employee=me.employee_id)
        request.session['zenvio_dept_line_id'] = line.id
        return {'url': '/odoo'}

    @http.route('/web/department/switch/back', type='jsonrpc', auth='user')
    def switch_back(self):
        session = request.session
        if session.get('zenvio_switch_origin_line'):
            # back to themselves, even if Can Switch was turned off meanwhile
            me = request.env['zenvio.department.employee'].sudo().browse(session['zenvio_switch_origin_line']).exists()
            if not (me and me.active and me.access_id.active and me.employee_id.active
                    and me.access_id.owner_id.id == session.uid):
                raise AccessError(_("Your own department login is no longer valid."))
            session.pop('zenvio_switch_origin_line', None)
            session['zenvio_dept_line_id'] = me.id
            return {'url': '/odoo'}
        origin = request.env['res.users'].sudo().browse(session.get('zenvio_switch_origin') or 0).exists()
        if not origin or not origin.active:
            raise AccessError(_("This session was not opened by an administrator."))
        session.pop('zenvio_dept_line_id', None)
        session.pop('zenvio_switch_origin', None)
        _become(origin)
        return {'url': '/odoo'}


class ZenvioDepartmentLogin(http.Controller):

    @http.route('/web/department/login', type='http', auth='none', readonly=False)
    def department_login(self, redirect=None, **kw):
        ensure_db()
        if request.env.uid is None:
            if request.session.uid is None:
                request.env['ir.http']._auth_method_public()
            else:
                request.update_env(user=request.session.uid)

        values = {'login_code': kw.get('login_code', ''), 'redirect': redirect}
        if request.httprequest.method == 'POST':
            login_code = (kw.get('login_code') or '').strip().upper()
            response, error = _department_login(_find_line(login_code), login_code, kw.get('password'), redirect=redirect)
            if response:
                return response
            values['error'] = error

        response = request.render('zenvio_department_login.department_login', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response
