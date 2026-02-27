/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class NozzleScreen extends Component {
    static template = "fuel_station.nozzle_screen";

    onBackClick() {
        this.env.services.action.doAction("fuel_station.fuel_dashboard_action_client");
    }
}

registry.category("actions").add("fuel_station.nozzle_screen", NozzleScreen);
