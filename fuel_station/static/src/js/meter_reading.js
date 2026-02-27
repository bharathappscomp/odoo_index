/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MeterReading extends Component {
    static template = "fuel_station.meter_reading";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            selectedDate: today,
            lines: [],
            total_sales: [],
            credit_sales: [],
            loading: false,
        });

        this.loadData();
    }

    async loadData() {
        this.state.loading = true;

        const data = await this.orm.call(
            "closing.entry",
            "get_meter_readings_by_date",
            [this.state.selectedDate]
        );

        // ✅ THIS IS THE ONLY CHANGE
        this.state.lines = data.meter_lines || [];
        this.state.total_sales = data.total_sales || [];
        this.state.credit_sales = data.credit_sales || [];

        this.state.loading = false;
    }

    onPrintPdf() {
        const data = {
            report_lines: this.state.lines || [],
            date: this.state.selectedDate,
        };

        return this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "fuel_station.meter_reading_report_template",
            report_file: "fuel_station.meter_reading_report_template",
            data: data,
        });
    }





    onDateChange(ev) {
        this.state.selectedDate = ev.target.value;
        this.loadData();
    }
}

registry.category("actions").add(
    "fuel_station.meter_reading",
    MeterReading
);
