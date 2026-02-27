/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

window.logged_employee_id = null;

export class UserLoginScreen extends Component {
    static template = "fuel_station.user_login_screen";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.emailRef = useRef("emailRef");
        this.passwordRef = useRef("passwordRef");
    }

    async onLogin() {

        const email = this.emailRef.el.value;
        const password = this.passwordRef.el.value;

        const employees = await this.orm.searchRead(
            "hr.employee",
            [["work_email", "=", email], ["password", "=", password]],
            ["id", "name"]
        );

        if (employees.length === 0) {
            this.notification.add("Invalid credentials!", { type: "danger" });
            return;
        }

        // 🔥 Save employee id globally
        window.logged_employee_id = employees[0].id;
        console.log("Saved Employee ID:", window.logged_employee_id);

        // Redirect
        this.action.doAction("fuel_station.action_user_screen");
    }
}

registry.category("actions").add("fuel_station.user_login_screen", UserLoginScreen);
