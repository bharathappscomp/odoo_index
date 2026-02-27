/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PettyCash extends Component {
    static template = "fuel_station.petty_cash";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            date: today,
            shifts: [],
        });

        onMounted(() => {
            this.loadShifts();
        });
    }

    async loadShifts() {
        // 1️⃣ Fetch open shifts for the date
        const records = await this.orm.searchRead(
            "fuel.shift.manager",
            [
                ["assigned_date", "=", this.state.date],
                ["state", "=", "open"],
            ],
            [
                "shift_id",
                "employee_id",
                "employee_coa_id",
            ]
        );

        if (!records.length) {
            this.state.shifts = [];
            return;
        }

        // 2️⃣ Collect unique employee IDs
        const employeeIds = [
            ...new Set(
                records
                    .map(r => r.employee_id?.[0])
                    .filter(Boolean)
            )
        ];

        // 3️⃣ Fetch employee petty cash balance
        const employees = await this.orm.searchRead(
            "hr.employee",
            [["id", "in", employeeIds]],
            ["petty_cash_balance"]
        );

        // 4️⃣ Build employee map {id: balance}
        const employeeBalanceMap = {};
        for (const emp of employees) {
            employeeBalanceMap[emp.id] = emp.petty_cash_balance || 0;
        }

        // 5️⃣ Deduplicate by shift + employee
        const uniqueMap = {};

        for (const rec of records) {
            const shiftId = rec.shift_id?.[0];
            const employeeId = rec.employee_id?.[0];

            if (!shiftId || !employeeId) continue;

            const key = `${shiftId}_${employeeId}`;

            if (!uniqueMap[key]) {
                uniqueMap[key] = {
                    id: key, // virtual ID for OWL
                    shift_id: rec.shift_id,
                    employee_id: rec.employee_id,
                    employee_coa_id: rec.employee_coa_id,
                    petty_cash_balance: employeeBalanceMap[employeeId] || 0,
                    amount: 0,
                };
            }
        }

        // 6️⃣ Assign to state
        this.state.shifts = Object.values(uniqueMap);
    }


    onAmountChange = (ev, row) => {
        row.amount = parseFloat(ev.target.value || 0);
    };

    createPettyCash = async (row) => {
        if (!row.amount || row.amount <= 0) {
            this.notification.add("Enter a valid amount", { type: "warning" });
            return;
        }

        try {
            await this.orm.call(
                "hr.employee",
                "create_petty_cash_record",
                [
                    [row.employee_id[0]],
                    row.amount,
                    row.shift_id[0],
                    this.state.date,
                    row.employee_id[1], // employee name
                ]
            );

            this.notification.add("Petty cash created successfully", {
                type: "success",
            });

            row.amount = 0;

            await this.loadShifts();

        } catch (error) {
            this.notification.add(
                error.message || "Error creating petty cash",
                { type: "danger" }
            );
        }
    };

    onDateChange(ev) {
        this.state.date = ev.target.value;
        this.loadShifts();
    }
}

registry.category("actions").add("fuel_station.petty_cash", PettyCash);
