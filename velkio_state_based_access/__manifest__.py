# -*- coding: utf-8 -*-
{
    'name': 'Velkio State Based Access',
    'version': '19.0.1.0.0',
    'summary': 'State-based form, list and kanban view rules for users and groups',
    'description': """
Velkio State Based Access
=========================

Configure form, list and kanban view behavior by model, record state, user or
group, and active company. Field modifiers and named button visibility apply
where supported by the view and widget. Notebook tabs, whole-form read-only
and chatter options belong to form views.
Rules can hide fields, make fields read-only or required, hide notebook pages
and buttons, make an entire form read-only, or hide its chatter.

Field, page, button, and whole-form behavior can be limited to selected values
of a selection or many2one state field. Rules apply per user after Odoo's shared
view cache and expressions are evaluated for each record in the web client.

This module controls the view interface. It does not replace Odoo access rights
or record rules for server-side data security. Chatter visibility is configured
per rule and is not state-dependent.
""",
    'author': 'Velkio',
    'maintainer': 'Velkio',
    'website': 'https://velkio.com',
    'support': 'velkio.odoosolution@gmail.com',
    'category': 'Administration',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/state_access_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
}
