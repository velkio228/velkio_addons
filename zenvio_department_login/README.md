# Zenvio Department Access

Department & role access control, one-click Switch User and secure employee code login for Odoo 19.

**Odoo 19 · Community and Enterprise · Technical name:** `zenvio_department_login`

## Setup
1. **Settings → Users** → open a user → **Department Access** tab → turn on **Top Management**.
2. **Add Department**: choose an existing department or type a new name; pick its icon and colour.
3. **Employees & Access** tab: add employees with their **Role** (User / Manager) and a password
   (at least 6 characters). Login codes are filled in for you.
4. **Access Rights** tab: set what **User Access** and **Manager Access** allow (see below).
5. Optional: 🔒 on an employee line gives that employee **Personal Access** (starts as a copy of
   the role); ↺ removes it.

## Access Rights (per role, or Personal Access per employee)
Access only takes rights away from the Top Management user, it never gives more.

| Where | Setting | Enforced |
|---|---|---|
| Top | Read-Only · Disable Relational Create/Edit | Server · Screen |
| Hide Menu | Menus (and sub-menus) hidden | Screen |
| Model Access | Read / Create / Edit / Delete | Server |
| Model Access | Hide Archive, Duplicate, Import, Export, Reports, Actions | Screen (import & export also server) |
| Field Access | Invisible, Read-Only, Required, Remove External Link (optionally per state) | Screen |
| Domain Access | Only these records (`employee`, `department`, `user` usable) | Server |
| Button/Tab Access | Hidden buttons and tabs (optionally per state) | Buttons: server · Tabs: screen |
| Hide Filter/Group By | Removed from the search panel | Screen |
| Chatter | Per model: chatter, send message, log notes, schedule activity | Posting & activities: server |
| Global | Same chatter switches, import, export, spreadsheet, add property for every model | Mostly server |
| Global | Disable Login · Disable Developer Mode | Server |

Employees never see or change the access setup, users, passwords, groups, modules or settings.

## Switch User
Top bar **Switch**: administrators (every department) and Top Management users (their own) open Odoo
as any employee without the password and come back with **Back**. On an employee line, **Can Switch**
lets that employee open others; **Switch Departments** limits which departments (empty: all of the
same Top Management user). Every switch is in the **Login Log** with who did it.

## Employee code login (shared terminals)
Employees sign in on the normal login page or `/web/department/login` with their login code and
password. The chatter shows the real employee. Five wrong passwords lock only that code for one
minute. Logins, failures and switches are recorded in **Login Log**.

## Move departments
User form → **Move Departments** (also offered when switching Top Management off): departments move
with their employees, codes, passwords and access to another Top Management user.

## Notes
* Odoo Enterprise: every person working in Odoo must be covered by your Odoo subscription.
* Passwords are stored hashed; nobody can read them back.
* An employee can be in several departments; each mapping has its own login code.

## Support
Zenvio – Odoo Solutions · <https://zenvio.com> · <mailto:zenvio.odoosolution@gmail.com>
License: OPL-1
