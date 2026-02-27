/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class CashSettlement extends Component {
    static template = "fuel_station.cash_settlement";

    setup() {
        this.orm = useService("orm");
        this.user = useService("user");

        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            shifts: [],
        pumps: [],
        nozzles: [],
        employees: [],

        selectedEmployee: null,
        isAdmin: false,

        selectedShifts: [],
        selectedPumps: [],
        selectedNozzles: [],
        date: today,

        cards: [],
        paymentsByShift: {},
        journals: [],
        loading: false,
        });

        this.fetchEntries = async () => {
            this.state.loading = true;

            const payload = {
                date: this.state.date || false,
                shift_ids: this.state.selectedShifts.map(s => s.id),
                pump_ids: this.state.selectedPumps.map(p => p.id),
                nozzle_ids: this.state.selectedNozzles.map(n => n.id),
                employee_id: this.state.selectedEmployee?.id || false,
            };

            const data = await this.orm.call(
                "closing.entry",
                "get_cash_settlement_entries",
                [payload]
            );

            this.state.cards = data;   // 🔥 cards = shift summaries
            this.state.loading = false;

            this.state.cards.forEach(card => {
                if (!this.state.paymentsByShift[card.shift_id]) {
                    this.state.paymentsByShift[card.shift_id] = [{
                        _uid: Date.now(),
                        amount: "",
                        journal_id: ""
                    }];
                }
            });
        };

        onWillStart(async () => {

            // 👑 admin check
            this.state.isAdmin = await this.user.hasGroup(
                "fuel_station.group_fuel_admin"
            );

            // 👤 current user's employee
            const [emp] = await this.orm.searchRead(
                "hr.employee",
                [["user_id", "=", this.user.userId]],
                ["id", "name"]
            );

            if (emp) {
                this.state.selectedEmployee = emp;
            }

            // 👥 load employees only for admin
            if (this.state.isAdmin) {
                this.state.employees = await this.orm.searchRead(
                    "hr.employee",
                    [],
                    ["id", "name"]
                );
            }

            await this.loadData();
            await this.fetchEntries();
        });

        // Filters (unchanged)
        this.onShiftSelect = (ev) => {
            const id = Number(ev.target.value);
            if (!id) return;
            const rec = this.state.shifts.find(r => r.id === id);
            if (rec && !this.state.selectedShifts.some(s => s.id === id)) {
                this.state.selectedShifts = [...this.state.selectedShifts, rec];
            }
            ev.target.value = "";
            this.fetchEntries();
        };

        this.onPumpSelect = (ev) => {
            const id = Number(ev.target.value);
            if (!id) return;
            const rec = this.state.pumps.find(r => r.id === id);
            if (rec && !this.state.selectedPumps.some(p => p.id === id)) {
                this.state.selectedPumps = [...this.state.selectedPumps, rec];
            }
            ev.target.value = "";
            this.fetchEntries();
        };

        this.onNozzleSelect = (ev) => {
            const id = Number(ev.target.value);
            if (!id) return;
            const rec = this.state.nozzles.find(r => r.id === id);
            if (rec && !this.state.selectedNozzles.some(n => n.id === id)) {
                this.state.selectedNozzles = [...this.state.selectedNozzles, rec];
            }
            ev.target.value = "";
            this.fetchEntries();
        };

        this.onRemoveShift = (ev) => {
            const id = Number(ev.currentTarget.dataset.id);
            this.state.selectedShifts =
                this.state.selectedShifts.filter(s => s.id !== id);
            this.fetchEntries();
        };

        this.onRemovePump = (ev) => {
            const id = Number(ev.currentTarget.dataset.id);
            this.state.selectedPumps =
                this.state.selectedPumps.filter(p => p.id !== id);
            this.fetchEntries();
        };

        this.onRemoveNozzle = (ev) => {
            const id = Number(ev.currentTarget.dataset.id);
            this.state.selectedNozzles =
                this.state.selectedNozzles.filter(n => n.id !== id);
            this.fetchEntries();
        };

        this.submitShiftSettlement = async (card) => {

            if (card._submitted) {
                return;
            }

            // 1️⃣ Collect payment lines
            const payments = this.state.paymentsByShift[card.shift_id] || [];

            if (!payments.length) {
                this.env.services.notification.add(
                    "Please enter payment details",
                    { type: "danger" }
                );
                return;
            }

            // ✅ DEFINE FIRST
            const paymentLines = payments.map(p => ({
                journal_id: p.journal_id,
                amount: Number(p.amount) || 0,
            }));

            // ✅ NOW VALIDATE
            if (paymentLines.some(p => !p.journal_id)) {
                this.env.services.notification.add(
                    "Please select journal for all payment lines",
                    { type: "danger" }
                );
                return;
            }

            // 3️⃣ Build payload
            const payload = {
                date: this.state.date,
                shift_id: card.shift_id,
                expected_amount: card.expected_amount,
                payment_lines: paymentLines,
                closing_entry_ids: card.closing_entry_ids,
                employee_id: this.state.selectedEmployee?.id,
            };

            // 4️⃣ Call backend
            try {
                await this.orm.call(
                    "closing.entry",
                    "action_submit_cash_settlement",
                    [payload]
                );

                // 5️⃣ Mark card as submitted (UI only)
                card._submitted = true;

                this.env.services.notification.add(
                    "Cash settlement submitted successfully",
                    { type: "success" }
                );

            } catch (err) {
                this.env.services.notification.add(
                    err.message || "Submission failed",
                    { type: "danger" }
                );
            }
        };

    }

    onEmployeeSelect(ev) {
        const id = Number(ev.target.value);
        if (!id) {
            this.state.selectedEmployee = null;
        } else {
            this.state.selectedEmployee =
                this.state.employees.find(e => e.id === id);
        }
        this.fetchEntries();
    }


    async loadData() {
        this.state.shifts = await this.orm.searchRead("fuel.station.shift", [], ["id", "name"]);
        this.state.pumps = await this.orm.searchRead("fuel.station.pump", [], ["id", "name"]);
        this.state.nozzles = await this.orm.searchRead("fuel.station.nozzle", [], ["id", "name"]);
        this.state.journals = await this.orm.searchRead(
            "account.journal",
            [["type", "in", ["cash", "bank"]]],
            ["id", "name"]
        );
    }

    getExpectedAmount(card) {
        return card.expected_amount || 0;
    }

    getClosingTotal(shiftId) {
        return (this.state.paymentsByShift[shiftId] || [])
            .reduce((sum, p) => sum + (Number(p.amount) || 0), 0);
    }

    addClosingLine(shiftId) {
        this.state.paymentsByShift[shiftId].push({
            _uid: crypto.randomUUID(),
            amount: 0,
            journal_id: ""
        });
    }

    removeClosingLine(shiftId, uid) {
        this.state.paymentsByShift[shiftId] =
            this.state.paymentsByShift[shiftId].filter(p => p._uid !== uid);
    }

}

registry.category("actions").add("fuel_station.cash_settlement", CashSettlement);
