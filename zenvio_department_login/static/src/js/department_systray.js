/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

/**
 * Top bar identity chip.
 * - Employee session: shows who is working (avatar, name, department) and,
 *   when an administrator opened it, the way back.
 * - Administrator / Top Management: "Switch" to open Odoo as any mapped
 *   employee of their departments, without the password.
 */
export class DepartmentIdentity extends Component {
    static template = "zenvio_department_login.DepartmentIdentity";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.notification = useService("notification");
        this.state = useState({ departments: [], loading: false, loaded: false, search: "" });
    }

    get info() {
        return session.zenvio_department;
    }

    get canSwitch() {
        return Boolean(session.zenvio_can_switch);
    }

    initials(name) {
        return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
    }

    tint(color) {
        return `o_zenvio_tint_${(color || 0) % 12}`;
    }

    async onOpened() {
        if (!this.canSwitch || this.state.loaded) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.departments = await rpc("/web/department/switch/targets");
            this.state.loaded = true;
        } finally {
            this.state.loading = false;
        }
    }

    get filtered() {
        const term = this.state.search.trim().toLowerCase();
        if (!term) {
            return this.state.departments;
        }
        return this.state.departments
            .map((dept) => {
                if (dept.name.toLowerCase().includes(term)) {
                    return dept;
                }
                const employees = dept.employees.filter((emp) =>
                    [emp.name, emp.code, emp.role].some((v) => (v || "").toLowerCase().includes(term))
                );
                return employees.length ? { ...dept, employees } : null;
            })
            .filter(Boolean);
    }

    async switchTo(employee) {
        if (employee.current) {
            return;
        }
        if (employee.login_disabled) {
            this.notification.add(_t("Login is disabled for %s's access.", employee.name), { type: "warning" });
            return;
        }
        const { url } = await rpc(`/web/department/switch/${employee.line_id}`);
        browser.location.href = url;
    }

    async backToAdmin() {
        const { url } = await rpc("/web/department/switch/back");
        browser.location.href = url;
    }

    signInAsAnother() {
        browser.location.href = "/web/session/logout?redirect=/web/department/login";
    }
}

// Menus are kept in localStorage, shared by every tab of this browser. When the
// browser switches between the Top Management user and an employee (or the
// employee's access changes), drop them so the menu service loads this
// session's own menus instead of showing someone else's first.
try {
    const owner = (session.zenvio_department && session.zenvio_department.access_key) || "";
    if (browser.localStorage.getItem("zenvio_menus_owner") !== owner) {
        browser.localStorage.removeItem("webclient_menus");
        browser.localStorage.removeItem("webclient_menus_version");
        browser.localStorage.setItem("zenvio_menus_owner", owner);
    }
} catch {
    // localStorage unavailable (private mode): the menu service fetches menus anyway
}

// "Hide Spreadsheet": spreadsheet modules may turn this back on in their own
// session_info (load order is not guaranteed), so switch it off before any view reads it.
if (session.zenvio_department?.hide_spreadsheet) {
    session.can_insert_in_spreadsheet = false;
}

if (session.zenvio_department || session.zenvio_can_switch) {
    registry.category("systray").add("zenvio_department_login.DepartmentIdentity", {
        Component: DepartmentIdentity,
    }, { sequence: 1 });
}
