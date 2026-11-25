"""Build the Odoo Apps page of Zenvio Department Access in the same layout as the other Zenvio apps.

Usage: python3 tools/build_department_presentation.py
Writes zenvio_department_login/static/description/index.html and copies the brand logo/mark.
banner.png and workflow.png are rendered separately (zenvio_brand/src/render_department.py).
"""
from html import escape
from pathlib import Path
import shutil

from build_app_presentation import para, heading, section, cards, button, callout
from inline_store_layout import inline_layout
from store_content import COMMON

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'zenvio_department_login'
DESC = MODULE / 'static' / 'description'
BRAND = ROOT / 'artwork' / 'branding'

APP = {
    'name': 'Zenvio Department Access',
    'version': '19.0.8.3.0',
    'license': 'OPL-1',
    'headline': 'One Odoo user for a whole department: every employee signs in with their own code and password.',
    'intro': ('Turn on Top Management for one Odoo user, then add your departments and the employees who work in them. '
              'Each employee signs in with their own login code and password through that single user, so you create '
              'no extra Odoo users, and each person works with exactly the menus, records and buttons their role allows.'),
    'chips': [
        'Departments and employees under one Top Management user',
        'A login code and password for every employee',
        'User and Manager access for each department',
        'One-click Switch User, with every login logged',
    ],
    'tiles': [
        ('Departments', 'Production, Stores, Sales ... with icon and colour'),
        ('Employees & codes', 'Own login code and hashed password'),
        ('Role access', 'User and Manager rules per department'),
        ('Personal access', 'Rules for one employee only'),
        ('Switch User', 'Open Odoo as any employee'),
        ('Login log', 'Every login, failure and switch'),
    ],
    'how': [
        ('One user', 'Turn on Top Management', 'Open Settings → Users, choose the user your team works through and switch on Top Management on the Department Access tab.'),
        ('Departments', 'Add departments', 'Pick an existing HR department or type a new name. Choose its icon and colour for the department card.'),
        ('Employees', 'Add employees', 'Add each employee with a role (User or Manager) and a password of at least 6 characters. The login code is filled in for you.'),
        ('Sign in', 'Employees log in', 'Employees type their code and password on the normal login page. They work as themselves: the chatter and the Login Log show the real person.'),
    ],
    'features': [
        ('Departments under one user', 'Every department belongs to a Top Management user. Its employees sign in through that user and never get more rights than that user has.'),
        ('Eight kinds of rules', 'Hide menus, limit models, fields and records, hide buttons and tabs, filters and group-bys, chatter actions, and global switches such as read-only.'),
        ('User and Manager roles', 'Each department has a User Access and a Manager Access. Give an employee a role and they get its rules straight away.'),
        ('Personal access', 'The lock button on an employee line gives that person rules of their own, starting as a copy of their role. Reset returns them to the role.'),
        ('Switch User', 'Administrators and Top Management users open Odoo as any of their employees without the password, see exactly what they see, then come back.'),
        ('Secure employee login', 'Hashed passwords, five wrong attempts lock only that code for a minute, and every login, failure and switch is kept in the Login Log.'),
    ],
    'rules': [
        ('Hide Menu', 'Screen', 'Menus are hidden together with all their sub-menus.'),
        ('Model Access', 'Server', 'Read, create, edit and delete per model, plus hide archive, duplicate, import, export, reports and actions.'),
        ('Field Access', 'Screen', 'Invisible, read-only, required or no link to the related record, optionally only in chosen states.'),
        ('Domain Access', 'Server', 'Only the records a rule allows, for example the employees of their own department.'),
        ('Button / Tab Access', 'Server & screen', 'Hide buttons and notebook tabs, optionally only in chosen states.'),
        ('Filters & Group By', 'Screen', 'Remove filters and group-bys from the search panel.'),
        ('Chatter', 'Server & screen', 'Hide the chatter, send message, log note or schedule activity, per model.'),
        ('Global', 'Server & screen', 'Read-only, no relational create/edit, no import, export or spreadsheet, disable login, disable developer mode.'),
    ],
    'scope': ('Access only ever takes rights away from the Top Management user, it never adds any. Employees never see or '
              'change the access setup, users, passwords, groups, modules or settings. Odoo Enterprise: every person '
              'working in Odoo must still be covered by your Odoo subscription.'),
    'requirements': [
        'Odoo 19 Community or Enterprise with the Employees (hr) app.',
        'An internal user to act as Top Management for each group of departments.',
        'Employees recorded in Odoo, or typed in while adding them to a department.',
    ],
    'steps': [
        ('Turn on Top Management', 'Settings → Users → open a user → Department Access tab → switch on Top Management.'),
        ('Add a department', 'Click Add Department, choose or type the department, and pick its icon and colour.'),
        ('Add employees', 'On Employees & Access, add employees with their role and a password. Add Department Employees adds everyone of that HR department at once.'),
        ('Set the access', 'On Access Rights, set what User Access and Manager Access allow, tab by tab.'),
        ('Give personal access', 'Optional: the lock on an employee line gives that person their own rules; reset brings back the role.'),
        ('Test with Switch', 'Use Switch in the top bar to open Odoo as the employee and check exactly what they see, then press Back.'),
    ],
    'workflow': [
        ('Login', 'Code and password', 'The employee signs in with their login code on the normal login page or on /web/department/login.'),
        ('Workspace', 'Only their access', 'Menus, records, fields and buttons follow their role or personal access.'),
        ('Activity', 'Their own name', 'Messages and notes show the real employee, not the shared user.'),
        ('Audit', 'Everything logged', 'Logins, failed attempts and switches are kept in the Login Log with IP address.'),
    ],
    'screenshots': [
        ('1_top_management.png', 'Top Management', 'Switch on Top Management on a user and add its departments as cards, each with its own icon and colour.'),
        ('2_department_employees.png', 'Employees & Access', 'Add the employees of a department with their role and password. Login codes are filled in automatically.'),
        ('3_access_model.png', 'Model Access', 'Choose per model what the role may read, create, edit or delete, and which list actions it sees.'),
        ('5_access_global.png', 'Global switches', 'Hide the chatter, import, export or spreadsheet everywhere, and disable login or developer mode with a single tick.'),
        ('6_switch_panel.png', 'Switch User', 'The top bar Switch lists departments and employees. One click opens Odoo as that employee.'),
        ('7_switched_employee.png', 'Working as the employee', 'The top bar shows who is working, in which department, and the way Back for the administrator.'),
    ],
    'troubleshooting': [
        ('Wrong employee code or password', 'Check the code on the employee line and set a new password there if needed. After five wrong passwords that code waits one minute.'),
        ('Login is disabled for your access', 'Disable Login is ticked on the role or personal access of that employee. Untick it on the Global tab.'),
        ('The employee was logged out', 'Their line, the employee, the department or its Top Management user changed or was archived. They sign in again.'),
        ('A code is refused', 'A login code cannot equal the login of an Odoo user. Choose another code for that employee.'),
        ('Top Management cannot be turned off', 'The user still has departments. Use Move Departments to hand them to another user first.'),
        ('No Switch in the top bar', 'Switch is for administrators and Top Management users. Tick Can Switch on an employee line to let that employee use it.'),
    ],
    'faqs': [
        ('Does the module create Odoo users?', 'No. Employees sign in through their Top Management user with their own code and password, so no user is created for them.'),
        ('Can an employee work in two departments?', 'Yes. Each department mapping has its own login code, so the code decides which department they open.'),
        ('Can an employee get more rights than the shared user?', 'No. Access only takes rights away from the Top Management user. It never adds any.'),
        ('How are passwords stored?', 'Hashed with the same password method as Odoo users. Nobody can read them back; you can only set a new one.'),
        ('Can employees change the setup?', 'No. Employees never see or change the access setup, users, passwords, groups, modules or settings.'),
        ('What about Odoo Enterprise licensing?', 'The module works on Community and Enterprise. On Enterprise, every person working in Odoo must be covered by your Odoo subscription.'),
    ],
}


def page(data):
    links = [('overview', 'Overview'), ('how', 'How it works'), ('features', 'Features'), ('rules', 'Access rules'),
             ('setup', 'Setup'), ('screenshots', 'Screenshots'), ('documentation', 'Documentation'), ('faq', 'FAQs'),
             ('support', 'Support')]
    chunks = ['<section class="oe_container" style="font-family:Arial,Helvetica,sans-serif;color:#282532;background-color:#FFFFFF;">',
              '<div class="container py-3">']
    chunks.append('<div class="row align-items-center mb-3"><div class="col-sm-4"><img src="zenvio_logo.png" alt="Zenvio Odoo Solutions logo" width="165" class="img-fluid"/></div><div class="col-sm-8 text-sm-right text-sm-end"><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Odoo 19</span><span class="badge p-2 m-1" style="color:#714B67;background-color:#F6F1F6;">Community &amp; Enterprise</span></div></div>')

    overview = f'<div class="text-center mb-4"><p style="font-size:12px;letter-spacing:2px;color:#9A7135;font-weight:700;">ZENVIO ODOO SOLUTIONS</p><h1 style="font-size:42px;line-height:1.15;font-weight:800;color:#282532;">{escape(data["name"])}</h1><p style="font-size:20px;line-height:1.5;color:#714B67;">{escape(data["headline"])}</p></div>'
    specs = [('19.0', 'Odoo version'), ('CE / EE', 'Editions'), ('Odoo.sh', 'Cloud deployment'), ('On-premise', 'Self-hosted'),
             (data['license'], 'Module license'), ('1 user', 'Many employees')]
    overview += '<div class="row mb-4">'
    for value, label in specs:
        overview += f'<div class="col-6 col-md-4 col-lg-2 mb-2"><div class="h-100 p-3 text-center rounded" style="background-color:#302236;"><div style="color:#E5BE7E;font-size:21px;font-weight:700;">{escape(value)}</div><div style="color:#F5EFF6;font-size:13px;">{escape(label)}</div></div></div>'
    overview += '</div><div class="row align-items-center"><div class="col-lg-6 mb-4">'
    overview += '<h2 style="font-size:27px;line-height:1.3;font-weight:700;color:#282532;">One user. Every department. Every employee.</h2>' + para(data['intro'])
    overview += '<ul class="pl-4" style="color:#514A59;font-size:16px;line-height:1.9;">' + ''.join('<li>' + escape(x) + '</li>' for x in data['chips']) + '</ul>'
    overview += button('How it works', '#how') + button('Setup guide', '#setup', True)
    overview += '</div><div class="col-lg-6 mb-4"><div class="p-3 rounded" style="background-color:#302236;"><div class="p-3 rounded" style="background-color:#FFFFFF;"><p style="color:#714B67;font-size:12px;font-weight:700;letter-spacing:1px;">EVERYTHING ON ONE SCREEN</p><div class="row">'
    for title, body in data['tiles']:
        overview += f'<div class="col-sm-6 mb-3"><div class="h-100 border rounded p-3" style="background-color:#F8F5F9;"><h3 style="font-size:18px;color:#714B67;">{escape(title)}</h3><p class="mb-0" style="font-size:14px;color:#625F6C;line-height:1.5;">{escape(body)}</p></div></div>'
    overview += '</div></div></div></div></div>'
    chunks.append(section('overview', overview, True))
    chunks.append('<div class="text-center p-2 my-3 border rounded" style="background-color:#FFFFFF;">' + ''.join(f'<a href="#{id_}" class="d-inline-block px-3 py-2" style="color:#714B67;font-size:14px;font-weight:700;">{label}</a>' for id_, label in links) + '</div>')
    chunks.append('<div class="my-4"><img src="banner.png" alt="' + escape(data['name'] + ': ' + ', '.join(data['chips'])) + '" class="img-fluid w-100 rounded"/></div>')

    how = heading('How it works', 'Create departments and employee logins with a single user') + '<div class="row">'
    for n, (label, title, body) in enumerate(data['how'], 1):
        how += f'<div class="col-md-6 col-lg-3 mb-3"><div class="h-100 border rounded p-3" style="background-color:#FFFFFF;"><p style="color:#9A7135;font-weight:700;font-size:12px;">{n:02d} / {escape(label.upper())}</p><h3 style="font-size:19px;color:#282532;">{escape(title)}</h3>{para(body)}</div></div>'
    how += '</div><img src="workflow.png" alt="One Top Management user holds several departments; each employee signs in with their own login code and password." class="img-fluid w-100 rounded border"/>'
    chunks.append(section('how', how, True))

    chunks.append(section('features', heading('Features', 'Everything a department needs, nothing more') + para('Set up departments, people and their access from the user form, then let each employee work with exactly what their role allows.') + cards(data['features'])))

    rules = heading('Access rules', 'Eight kinds of rules, per role or per employee') + '<div class="row">'
    for title, where, body in data['rules']:
        rules += f'<div class="col-md-6 col-lg-3 mb-3"><div class="h-100 p-4 border rounded" style="background-color:#FFFFFF;"><p class="mb-3" style="font-size:12px;color:#714B67;font-weight:700;">ENFORCED: {escape(where.upper())}</p><h3 style="color:#282532;font-size:21px;">{escape(title)}</h3>{para(body)}</div></div>'
    rules += '</div><div class="p-3 border rounded" style="background-color:#FFFFFF;"><h3 style="font-size:18px;color:#714B67;">Understand the scope</h3>' + para(data['scope'], 'mb-0') + '</div>'
    chunks.append(section('rules', rules, True))
    chunks.append(callout('Set up your first department in minutes', 'Turn on Top Management, add a department and its employees, then check the result with Switch User.', '#setup', 'Read the setup guide'))

    requirements = ''.join('<li class="mb-2">' + escape(r) + '</li>' for r in data['requirements'])
    setup = heading('Getting started', 'Six steps from one user to a working team') + '<div class="p-3 p-md-4 border rounded mb-4" style="background-color:#F8F5EF;"><h3 style="font-size:21px;color:#282532;">Before installation</h3>' + para(COMMON['hosting']) + f'<ul style="color:#625F6C;font-size:16px;line-height:1.8;">{requirements}</ul></div>' + cards(data['steps'], 'col-md-6')
    chunks.append(section('setup', setup))

    flow = heading('Daily operation', 'What happens when an employee signs in') + '<div class="row">'
    for n, (label, title, body) in enumerate(data['workflow'], 1):
        flow += f'<div class="col-md-6 col-lg-3 mb-3"><div class="h-100 border rounded p-3" style="background-color:#FFFFFF;"><p style="color:#9A7135;font-weight:700;font-size:12px;">{n:02d} / {escape(label.upper())}</p><h3 style="font-size:19px;color:#282532;">{escape(title)}</h3>{para(body)}</div></div>'
    chunks.append(section('workflow', flow + '</div>', True))

    gallery = heading('Product walkthrough', 'See it on screen') + para('Screenshots of the module in a demonstration database. Select an image to view it at full size.')
    for n, (file, title, body) in enumerate(data['screenshots']):
        assert (DESC / 'screenshots' / file).is_file(), file
        gallery += f'<div class="row align-items-center my-4 py-3 border-bottom"><div class="col-lg-4 {"order-lg-2" if n % 2 else ""}"><p style="color:#9A7135;font-size:12px;font-weight:700;">SCREEN {n + 1:02d}</p><h3 style="color:#282532;font-size:24px;">{escape(title)}</h3>{para(body)}</div><div class="col-lg-8 {"order-lg-1" if n % 2 else ""}"><a href="screenshots/{file}"><img src="screenshots/{file}" alt="{escape(title)}: demonstration screenshot" class="img-fluid w-100 border rounded"/></a></div></div>'
    chunks.append(section('screenshots', gallery))

    docs = heading('Documentation', 'Your guides, in one place') + '<div class="row">'
    for title, body, target, label in [('Setup guide', 'Requirements and the six setup steps.', '#setup', 'Open setup guide'),
                                       ('Access rules', 'What each of the eight rule types does and where it applies.', '#rules', 'View access rules'),
                                       ('Troubleshooting', 'Logins, codes, switching and moving departments.', '#troubleshooting', 'Find an answer')]:
        docs += f'<div class="col-md-4 mb-3"><div class="h-100 p-4 border rounded" style="background-color:#FFFFFF;"><h3 style="font-size:21px;color:#282532;">{title}</h3>{para(body)}<a href="{target}" style="color:#714B67;font-weight:700;">{label} →</a></div></div>'
    chunks.append(section('documentation', docs + '</div>', True))
    chunks.append(section('troubleshooting', heading('Troubleshooting', 'When a login or a rule needs attention') + cards(data['troubleshooting'])))

    faq = heading('Questions & answers', 'Check the details before you install') + '<div class="row">'
    for n, (q, a) in enumerate(data['faqs'], 1):
        faq += f'<div class="col-md-6 mb-3"><div class="h-100 border rounded p-4"><p style="font-size:12px;color:#9A7135;font-weight:700;">{n:02d}</p><h3 style="font-size:19px;color:#282532;">{escape(q)}</h3>{para(a)}</div></div>'
    chunks.append(section('faq', faq + '</div>'))

    support = heading('Zenvio support', 'Get help with your departments') + cards([
        ('Setup questions', 'Tell us how your departments and users are organised and the step you need help with.'),
        ('Login or access issues', 'Share the employee code (not the password), the action and the exact message.'),
        ('Rules & configuration', 'Ask which rule type fits what you want to hide or limit.')])
    support += callout('Tell us what you need help with', 'Include your Odoo and module versions. Remove passwords and personal data from shared screenshots.', 'mailto:' + COMMON['email'], 'Email Zenvio support')
    support += f'<div class="row align-items-center"><div class="col-md-4"><img src="zenvio_logo.png" alt="Zenvio Odoo Solutions" width="180" class="img-fluid"/></div><div class="col-md-8">{para(COMMON["email"])}{para("Zenvio Department Access by Zenvio Odoo Solutions.", "small")}</div></div>'
    chunks.append(section('support', support, True))
    chunks.append(section('release', heading('Release information', 'Version ' + data['version']) + para('Department access with User and Manager roles, personal access, eight rule types, Switch User, employee code login and Login Log. License: ' + data['license'] + '.')))
    chunks.extend(['</div>', '</section>'])
    return '\n'.join(chunks) + '\n'


def build():
    for source, target in [('zenvio-precision-logo.png', 'zenvio_logo.png'), ('zenvio-precision-mark.png', 'zenvio_mark.png')]:
        shutil.copy2(BRAND / source, DESC / target)
    (DESC / 'index.html').write_text(inline_layout(page(APP)), encoding='utf-8')
    print(DESC / 'index.html')


if __name__ == '__main__':
    build()
