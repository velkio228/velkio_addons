import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { colorPickerField } from "@web/views/fields/color_picker/color_picker_field";

class DepartmentIcon extends Component {
    static template = "zenvio_department_login.DepartmentIcon";
    static props = { ...standardFieldProps };

    get options() {
        return this.props.record.fields[this.props.name].selection;
    }

    select(value) {
        if (!this.props.readonly) {
            return this.props.record.update({ [this.props.name]: value });
        }
    }
}

class PasswordStatus extends Component {
    static template = "zenvio_department_login.PasswordStatus";
    static props = { ...standardFieldProps };
}

registry.category("fields").add("zenvio_department_icon", {
    component: DepartmentIcon,
    supportedTypes: ["selection"],
});
registry.category("fields").add("zenvio_password_status", {
    component: PasswordStatus,
    supportedTypes: ["boolean"],
});
registry.category("fields").add("zenvio_department_color", {
    ...colorPickerField,
    extractProps: () => ({ canToggle: false }),
});
