/** @odoo-module **/

import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CustomerOutstanding extends Component {
    static template = "fuel_station.customer_outstanding";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            start_date: today,
            end_date: today,
            customers: [],
            customer_id: "",
            data: [],
            loading: false,
        });

        onWillStart(async () => {
            this.state.customers = await this.orm.searchRead(
                "res.partner",
                [["is_credit_customer", "=", true]],
                ["name"]
            );
        });

        // ✅ AUTO LOAD when filters change
        useEffect(
            () => {
                if (this.state.start_date && this.state.end_date) {
                    this.loadData();
                }
            },
            () => [this.state.start_date, this.state.end_date, this.state.customer_id]
        );
    }

    async loadData() {
        this.state.loading = true;

        this.state.data = await this.orm.call(
            "res.partner",
            "get_customer_outstanding_data",
            [
                this.state.start_date,
                this.state.end_date,
                this.state.customer_id ? [parseInt(this.state.customer_id)] : []
            ]
        );

        this.state.loading = false;
    }

    printReport() {
        this.actionService.doAction({
            type: "ir.actions.report",
            report_name: "fuel_station.report_customer_outstanding_template",
            report_type: "qweb-pdf",
            data: {
                form: {
                    start_date: this.state.start_date,
                    end_date: this.state.end_date,
                    partner_ids: this.state.customer_id
                        ? [parseInt(this.state.customer_id)]
                        : [],
                }
            }
        });
    }
}

registry.category("actions").add(
    "fuel_station.customer_outstanding",
    CustomerOutstanding
);
