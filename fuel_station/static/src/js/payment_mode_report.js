/** @odoo-module **/

import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PaymentMode extends Component {
    static template = "fuel_station.payment_mode";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            start_date: today,
            end_date: today,
            journals: [],
            journal_id: "",

            rows: [],
            journal_summary: {},
            pump_summary: {},
            nozzle_summary: {},
            total: 0,
            loading: false,
        });

        onWillStart(async () => {
            this.state.journals = await this.orm.searchRead(
                "account.journal",
                [["type", "in", ["cash", "bank"]]],
                ["name"]
            );
        });

        // 🔄 Auto reload when filters change
        useEffect(
            () => {
                this.loadData();
            },
            () => [this.state.start_date, this.state.end_date, this.state.journal_id]
        );
    }

    async loadData() {
        if (!this.state.start_date || !this.state.end_date) return;

        this.state.loading = true;

        const result = await this.orm.call(
            "account.payment",
            "get_payment_mode_data",
            [
                this.state.start_date,
                this.state.end_date,
                this.state.journal_id ? [parseInt(this.state.journal_id)] : [],
            ]
        );

        this.state.rows = result.rows;
        this.state.journal_summary = result.journal_summary;
        this.state.pump_summary = result.pump_summary;
        this.state.nozzle_summary = result.nozzle_summary;
        this.state.total = result.total;

        this.state.loading = false;
    }

    printReport() {
        this.actionService.doAction({
            type: "ir.actions.report",
            report_name: "fuel_station.report_payment_mode_template",
            report_type: "qweb-pdf",
            data: {
                form: {
                    start_date: this.state.start_date,
                    end_date: this.state.end_date,
                    journal_ids: this.state.journal_id
                        ? [parseInt(this.state.journal_id)]
                        : [],
                }
            }
        });
    }
}

registry.category("actions").add(
    "fuel_station.payment_mode",
    PaymentMode
);
