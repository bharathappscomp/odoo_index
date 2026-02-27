/** @odoo-module **/

import { Component, useState, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ShiftReport extends Component {
    static template = "fuel_station.shift_report";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            start_date: today,
            end_date: today,
            shiftData: {},
            loading: false,
        });

        // ✅ AUTO LOAD when dates change
        useEffect(
            () => {
                if (this.state.start_date && this.state.end_date) {
                    this.loadData();
                }
            },
            () => [this.state.start_date, this.state.end_date]
        );
    }

    async loadData() {
        this.state.loading = true;

        this.state.shiftData = await this.orm.call(
            "closing.entry",
            "get_shift_wise_data",
            [this.state.start_date, this.state.end_date]
        );

        this.state.loading = false;
    }

    generateReport() {
        if (!this.state.start_date || !this.state.end_date) {
            this.notification.add(
                "Please select Start Date and End Date",
                { type: "warning" }
            );
            return;
        }

        this.actionService.doAction({
            type: "ir.actions.report",
            report_name: "fuel_station.report_shift_wise_template",
            report_type: "qweb-pdf",
            data: {
                form: {
                    start_date: this.state.start_date,
                    end_date: this.state.end_date,
                }
            }
        });
    }
}

registry.category("actions").add(
    "fuel_station.shift_report",
    ShiftReport
);
