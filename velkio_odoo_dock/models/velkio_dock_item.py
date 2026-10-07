import json
import logging
import re
from collections import defaultdict

from odoo import api, fields, models

from .res_users import DOCK_ICON_SIZES, DOCK_OVERVIEW_THEMES, DOCK_POSITIONS, DOCK_STYLES

_logger = logging.getLogger(__name__)

RECENT_MAX = 20
RECENT_RECORDS_MAX = 15
FAVORITES_MAX = 30
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
BOOL_SETTINGS = {
    "autohide": "velkio_dock_autohide",
    "show_recent": "velkio_dock_show_recent",
    "magnify": "velkio_dock_magnify",
    "shortcuts": "velkio_dock_shortcuts",
    "show_badges": "velkio_dock_show_badges",
    "show_favorites": "velkio_dock_show_favorites",
}


class VelkioDockItem(models.Model):
    _name = "velkio.dock.item"
    _description = "Velkio Dock Item"
    _order = "sequence, id"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        ondelete="cascade",
        index=True,
    )
    menu_id = fields.Many2one(
        "ir.ui.menu",
        string="App",
        required=True,
        ondelete="cascade",
        domain=[("parent_id", "=", False)],
    )
    sequence = fields.Integer(default=10)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _dock_user(self):
        return self.env.user.sudo()

    @api.model
    def _parse_ids(self, raw):
        return [int(x) for x in (raw or "").split(",") if x.strip().isdigit()]

    @api.model
    def _visible_menu_ids(self, menu_ids, root_only=False):
        """Return requested menu ids that are visible to the current user."""
        ordered = list(dict.fromkeys(int(mid) for mid in (menu_ids or []) if str(mid).isdigit()))
        if not ordered:
            return []
        domain = [("id", "in", ordered)]
        if root_only:
            domain.append(("parent_id", "=", False))
        # A plain menu search does not enforce Odoo's group/action visibility.
        # Keep the current user so hidden menus and inaccessible actions are excluded.
        visible = set(self.env["ir.ui.menu"].search(domain)._filter_visible_menus().ids)
        return [mid for mid in ordered if mid in visible]

    @api.model
    def _get_recent_ids(self):
        return self._visible_menu_ids(self._parse_ids(self._dock_user().velkio_dock_recent_ids), root_only=True)

    @api.model
    def _get_favorite_ids(self):
        return self._visible_menu_ids(self._parse_ids(self._dock_user().velkio_dock_fav_menu_ids))

    @api.model
    def _load_recent_records(self):
        try:
            records = json.loads(self._dock_user().velkio_dock_recent_records or "[]")
        except ValueError:
            return []
        if not isinstance(records, list):
            return []
        return [
            r for r in records
            if isinstance(r, dict)
            and isinstance(r.get("model"), str)
            and r["model"]
            and type(r.get("id")) is int
            and r["id"] > 0
        ][:RECENT_RECORDS_MAX]

    @api.model
    def _save_recent_records(self, records):
        self._dock_user().velkio_dock_recent_records = json.dumps(records[:RECENT_RECORDS_MAX])

    @api.model
    def _get_recent_records(self):
        """Recent records the user can still read (deleted ones are dropped)."""
        records = self._load_recent_records()
        current_names = {}
        by_model = defaultdict(list)
        for rec in records:
            by_model[rec["model"]].append(rec["id"])
        for model_name, ids in by_model.items():
            if model_name not in self.env:
                continue
            Model = self.env[model_name]
            if not Model.has_access("read"):
                continue
            for rec in Model.browse(ids).exists()._filtered_access("read"):
                current_names[(model_name, rec.id)] = str(rec.display_name or "").strip()[:200]
        return [
            {**r, "name": current_names[(r["model"], r["id"])]}
            for r in records if current_names.get((r["model"], r["id"]))
        ]

    @api.model
    def _get_settings(self):
        user = self._dock_user()
        settings = {
            "position": user.velkio_dock_position or "left",
            "style": user.velkio_dock_style or "dark",
            "icon_size": user.velkio_dock_icon_size or "medium",
            "recent_limit": user.velkio_dock_recent_limit or 0,
            "accent_color": user.velkio_dock_accent_color or "#E95420",
            "overview_theme": user.velkio_dock_overview_theme or "auto",
        }
        for key, fname in BOOL_SETTINGS.items():
            settings[key] = bool(user[fname])
        return settings

    # ------------------------------------------------------------------
    # public API used by the dock (JS)
    # ------------------------------------------------------------------
    @api.model
    def get_dock(self):
        """Everything the dock needs in one call."""
        user = self._dock_user()
        if user.velkio_dock_configured:
            menu_ids = self.search([("user_id", "=", self.env.uid)]).mapped("menu_id").ids
        else:
            menu_ids = []
        # Previously saved pins may become inaccessible after a permissions
        # change. Filter every response, not only new writes.
        menu_ids = self._visible_menu_ids(menu_ids, root_only=True)
        return {
            "configured": bool(user.velkio_dock_configured),
            "menu_ids": menu_ids,
            "recent_ids": self._get_recent_ids(),
            "favorite_ids": self._get_favorite_ids(),
            "recent_records": self._get_recent_records(),
            "settings": self._get_settings(),
        }

    @api.model
    def set_dock(self, menu_ids):
        """Replace the current user's pinned apps with ``menu_ids`` (ordered)."""
        menu_ids = [int(m) for m in (menu_ids or [])]
        ordered = self._visible_menu_ids(menu_ids, root_only=True)

        self.search([("user_id", "=", self.env.uid)]).unlink()
        self.create(
            [
                {"user_id": self.env.uid, "menu_id": mid, "sequence": index}
                for index, mid in enumerate(ordered)
            ]
        )
        self._dock_user().velkio_dock_configured = True
        return self.get_dock()

    # ---------------- recent apps ----------------
    @api.model
    def push_recent(self, menu_id):
        """Move ``menu_id`` to the front of the user's recent apps."""
        try:
            menu_id = int(menu_id)
        except (TypeError, ValueError):
            return False
        if menu_id not in self._visible_menu_ids([menu_id], root_only=True):
            return False
        recent = [menu_id] + [m for m in self._get_recent_ids() if m != menu_id]
        self._dock_user().velkio_dock_recent_ids = ",".join(map(str, recent[:RECENT_MAX]))
        return True

    @api.model
    def remove_recent(self, menu_id):
        menu_id = int(menu_id)
        recent = [m for m in self._get_recent_ids() if m != menu_id]
        self._dock_user().velkio_dock_recent_ids = ",".join(map(str, recent))
        return True

    @api.model
    def clear_recent(self):
        self._dock_user().velkio_dock_recent_ids = False
        return True

    # ---------------- favourite menus ----------------
    @api.model
    def set_favorites(self, menu_ids):
        menu_ids = [int(m) for m in (menu_ids or [])]
        ordered = self._visible_menu_ids(menu_ids)[:FAVORITES_MAX]
        self._dock_user().velkio_dock_fav_menu_ids = ",".join(map(str, ordered))
        return ordered

    # ---------------- recent records ----------------
    @api.model
    def push_recent_record(self, vals):
        vals = vals or {}
        model_name = vals.get("model")
        try:
            res_id = int(vals.get("id"))
        except (TypeError, ValueError):
            return False
        if not isinstance(model_name, str) or model_name not in self.env or res_id <= 0:
            return False
        Model = self.env[model_name]
        if not Model.has_access("read"):
            return False
        record = Model.browse(res_id).exists()._filtered_access("read")
        if not record:
            return False
        # Never trust a client-supplied display name for a recent record.
        name = str(record.display_name or "").strip()[:200]
        if not name:
            return False
        app_id = vals.get("app_id")
        try:
            app_id = int(app_id) if app_id else False
        except (TypeError, ValueError):
            app_id = False
        if app_id and app_id not in self._visible_menu_ids([app_id], root_only=True):
            app_id = False
        entry = {
            "model": model_name,
            "id": res_id,
            "name": name,
            "model_name": self.env["ir.model"]._get(model_name).name or model_name,
            "app_id": app_id,
        }
        records = [
            r for r in self._load_recent_records()
            if not (r["model"] == model_name and r["id"] == res_id)
        ]
        self._save_recent_records([entry] + records)
        return entry

    @api.model
    def remove_recent_record(self, model_name, res_id):
        records = [
            r for r in self._load_recent_records()
            if not (r["model"] == model_name and r["id"] == int(res_id))
        ]
        self._save_recent_records(records)
        return True

    @api.model
    def clear_recent_records(self):
        self._dock_user().velkio_dock_recent_records = False
        return True

    # ---------------- notification badges ----------------
    @api.model
    def _menu_id_from_xmlid(self, xmlid):
        menu = self.env.ref(xmlid, raise_if_not_found=False)
        return menu.id if menu and menu._name == "ir.ui.menu" else False

    @api.model
    def _root_menus_for_models(self, model_names):
        """Map model name -> the root menu (app) whose menus open that model."""
        result = {}
        if not model_names:
            return result
        actions = self.env["ir.actions.act_window"].sudo().search(
            [("res_model", "in", list(model_names))]
        )
        if not actions:
            return result
        model_by_action = {a.id: a.res_model for a in actions}
        # non-sudo search: only menus this user may see
        menus = self.env["ir.ui.menu"].search(
            [("action", "in", ["ir.actions.act_window,%d" % a for a in actions.ids])]
        )
        votes = defaultdict(lambda: defaultdict(int))
        for menu in menus:
            root_id = int(menu.parent_path.split("/")[0]) if menu.parent_path else menu.id
            votes[model_by_action[menu.action.id]][root_id] += 1
        for model_name, roots in votes.items():
            result[model_name] = max(roots, key=roots.get)
        return result

    @api.model
    def _discuss_unread_count(self):
        partner = self.env.user.partner_id
        count = partner._get_needaction_count()
        members = self.env["discuss.channel.member"].search(
            [("partner_id", "=", partner.id), ("is_pinned", "=", True)]
        )
        for member in members:
            if not member.message_unread_counter:
                continue
            if member.channel_id.channel_type in ("chat", "group"):
                count += member.message_unread_counter
            else:
                count += 1
        return count

    @api.model
    def get_badges(self):
        """{menu_id: count} — unread Discuss messages, due To-dos, due activities."""
        badges = defaultdict(int)
        if "mail.activity" not in self.env:
            return {}
        try:
            groups = self.env["res.users"]._get_activity_groups()
            due = {
                g["model"]: g.get("today_count", 0) + g.get("overdue_count", 0)
                for g in groups
                if g.get("model") and g["model"] != "mail.activity"
            }
            due = {m: c for m, c in due.items() if c}
            for model_name, root_id in self._root_menus_for_models(due).items():
                badges[root_id] += due[model_name]
        except Exception:
            _logger.exception("Velkio dock: could not compute activity badges")

        if "discuss.channel.member" in self.env:
            discuss = self._menu_id_from_xmlid("mail.menu_root_discuss")
            if discuss:
                try:
                    badges[discuss] = self._discuss_unread_count()
                except Exception:
                    _logger.exception("Velkio dock: could not compute Discuss badge")

        todo = self._menu_id_from_xmlid("project_todo.menu_todo_todos")
        if todo and "project.task" in self.env and self.env["project.task"].has_access("read"):
            try:
                badges[todo] = self.env["project.task"].search_count([
                    ("project_id", "=", False),
                    ("user_ids", "in", self.env.uid),
                    ("state", "not in", ["1_done", "1_canceled"]),
                    ("date_deadline", "<=", fields.Datetime.now()),
                ])
            except Exception:
                _logger.exception("Velkio dock: could not compute To-do badge")
        return {mid: count for mid, count in badges.items() if count}

    # ---------------- settings ----------------
    @api.model
    def set_settings(self, settings):
        """Save dock appearance settings (validated whitelist)."""
        settings = settings or {}
        vals = {}
        if settings.get("position") in dict(DOCK_POSITIONS):
            vals["velkio_dock_position"] = settings["position"]
        if settings.get("style") in dict(DOCK_STYLES):
            vals["velkio_dock_style"] = settings["style"]
        if settings.get("icon_size") in dict(DOCK_ICON_SIZES):
            vals["velkio_dock_icon_size"] = settings["icon_size"]
        if settings.get("overview_theme") in dict(DOCK_OVERVIEW_THEMES):
            vals["velkio_dock_overview_theme"] = settings["overview_theme"]
        for key, fname in BOOL_SETTINGS.items():
            if key in settings:
                vals[fname] = bool(settings[key])
        if "recent_limit" in settings:
            try:
                vals["velkio_dock_recent_limit"] = max(0, min(15, int(settings["recent_limit"])))
            except (TypeError, ValueError):
                pass
        color = settings.get("accent_color")
        if isinstance(color, str) and COLOR_RE.match(color):
            vals["velkio_dock_accent_color"] = color
        if vals:
            self._dock_user().write(vals)
        return self._get_settings()
