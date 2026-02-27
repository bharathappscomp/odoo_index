/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class UserScreen extends Component {
    static template = "fuel_station.user_screen";

    setup() {
        this.orm = useService("orm");
        this.user = this.env.services.user;
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        const today = new Date().toISOString().slice(0,10);

        this.state = useState({
            shift_manager: [],
            selected_date: today,
            today: today,
            // ⭐ CREDIT: store credit lines per shift
            creditData: {},
            loyaltyData: {},
        });

        onMounted(async () => {
            this.is_admin = await this.user.hasGroup("fuel_station.group_fuel_admin");

            await this.loadShiftDetails();
        });
    }

    isAlive() {
        return !this.__owl__.isDestroyed;
    }

    /* ============================================================================
       LOAD SHIFT DETAILS (UNCHANGED)
    ============================================================================ */
    async loadShiftDetails() {
        // 🔥 YOUR ORIGINAL CODE — NOT TOUCHED
        const selectedDate = this.state.selected_date;

        let domain = [["assigned_date", "=", selectedDate]];
        if (!this.is_admin) {
            domain.push(["employee_id.user_id", "=", this.user.userId]);
        }

        const records = await this.orm.searchRead(
            "fuel.shift.manager",
            domain,
            [
                "id",
                "nozzle_id",
                "pump_id",
                "shift_id",
                "employee_id",
                "state",
                "start_reading",
                "end_reading",
                "fuel_id",
                "dip_test",
                "dip_taken_qty",
                "dip_returned_qty",
            ]
        );

        if (!this.isAlive()) return;

        let result = [];

        /* STEP 1: Normalize */
        for (let r of records) {
            const shiftId = r.id;

            result.push({
                id: shiftId,
                shift_id: r.shift_id?.[0],
                shift_name: r.shift_id?.[1],
                employee_id: r.employee_id?.[0],
                employee_name: r.employee_id?.[1],
                nozzle_id: r.nozzle_id?.[0],
                nozzle_name: r.nozzle_id?.[1],
                pump_id: r.pump_id?.[0],
                pump_name: r.pump_id?.[1],
                fuel_id: r.fuel_id?.[0],
                fuel_name: r.fuel_id?.[1],
                fuel_price: 0,
                /* ⭐ DIP TEST */
                dip_test: r.dip_test || false,
                dip_taken_qty: r.dip_taken_qty || 0,
                dip_returned_qty: r.dip_returned_qty || 0,
                state: r.state,
                start_reading: r.start_reading || "",
                end_reading: r.end_reading || "",
                prev_shift_warning: "",
            });

            for (const r of result) {
                if (!r.fuel_id) continue;

                const [product] = await this.orm.searchRead(
                    "product.product",
                    [["id", "=", r.fuel_id]],
                    ["list_price"]
                );

                r.fuel_price = parseFloat(product?.list_price || 0);
            }
        }

        for (const s of result) {
            // If shift is CLOSED → load from backend
            if (s.state === "close") {

                const loyaltyLines = await this.orm.searchRead(
                    "closing.loyalty.line",
                    [["closing_entry_id.shift_manager_id", "=", s.id]],
                    ["customer_id", "quantity"]
                );

                this.state.loyaltyData[s.id] = loyaltyLines.map(l => ({
                    customer_id: l.customer_id?.[0] || null,
                    quantity: l.quantity || 0,
                    use_reward: l.use_reward || false,
                    selected_reward_id: l.selected_reward_id || null,
                    available_rewards: l.available_rewards || [],
                    _uid: crypto.randomUUID(),
                }));
            }

        }

        /* Load all shifts once */
        const allShifts = await this.orm.searchRead(
            "fuel.station.shift",
            [],
            ["id", "name", "sequence"]
        );

        const shiftSeqMap = {};
        for (let sh of allShifts) {
            shiftSeqMap[sh.id] = { name: sh.name, seq: sh.sequence };
        }

        /* STEP 3: Check previous shift status */
        for (let r of result) {
            const seq = shiftSeqMap[r.shift_id]?.seq || 0;

            if (seq <= 1) continue;

            const prevShiftSeq = seq - 1;
            const prevShift = allShifts.find(s => s.sequence === prevShiftSeq);
            if (!prevShift) continue;

            const prevManager = await this.orm.searchRead(
                "fuel.shift.manager",
                [
                    ["shift_id", "=", prevShift.id],
                    ["assigned_date", "=", selectedDate],
                    ["nozzle_id", "=", r.nozzle_id],
                ],
                ["state", "employee_id"]
            );

            if (prevManager.length && prevManager[0].state !== "close") {
                r.prev_shift_warning =
                    `Previous ${prevShift.name} for ${r.nozzle_name} is not closed by ${prevManager[0].employee_id?.[1]}.`;
            }
        }

        /* STEP 4: Compute Start Reading */
        /* ============================================================================
           STEP 4: Compute Start Reading (ACROSS DAYS)
        ============================================================================ */
        for (let r of result) {
            const seq = shiftSeqMap[r.shift_id]?.seq || 0;

            if (r.state === "close") continue;
            if (r.start_reading) continue;

            // Find LAST closed shift for this nozzle BEFORE or ON selected date
            const prevClose = await this.orm.searchRead(
                "fuel.shift.manager",
                [
                    ["nozzle_id", "=", r.nozzle_id],
                    ["state", "=", "close"],
                    ["assigned_date", "<=", selectedDate], // ✅ KEY FIX
                ],
                ["end_reading", "assigned_date"],
                {
                    order: "assigned_date desc, id desc",
                    limit: 1,
                }
            );

            r.start_reading = prevClose.length ? prevClose[0].end_reading : "";
        }

        this.state.shift_manager = result;
    }

    /* ============================================================================
       ON DATE CHANGE
    ============================================================================ */
    async onDateChange(ev) {
        const selectedDate = ev.target.value;
        const today = this.state.today;

        if (selectedDate > today) {
            this.notification.add(
                "Future dates are not allowed.",
                { type: "danger" }
            );

            // Reset back to today
            this.state.selected_date = today;
            ev.target.value = today;
            return;
        }

        this.state.selected_date = selectedDate;
        await this.loadShiftDetails();
    }


    /* ============================================================================
       ⭐ CREDIT: OPEN POPUP
    ============================================================================ */
    async openCreditPopup(ev) {
        const shiftId = parseInt(ev.currentTarget.dataset.shift);
        const record = this.state.shift_manager.find(s => s.id === shiftId);

        if (!record) return;

        let creditLines = [];

        // 🔒 SHIFT CLOSED → LOAD FROM BACKEND (READ ONLY)
        if (record.state === "close") {
            creditLines = await this.orm.searchRead(
                "credit.sale.line",
                [["closing_entry_id.shift_manager_id", "=", record.id]],
                ["customer_id", "vehicle_no", "quantity", "amount"]
            );

            // normalize for dialog
            creditLines = creditLines.map(l => ({
                customer_id: l.customer_id?.[0] || null,
                vehicle_no: l.vehicle_no || "",
                quantity: l.quantity || 0,
                amount: l.amount || 0,
                _vehicles: [],
                _uid: crypto.randomUUID(),   // ⭐ REQUIRED
            }));

            for (const line of creditLines) {
                if (!line.customer_id) continue;
                const vehicles = await this.orm.searchRead(
                    "credit.vehicle.line",
                    [["credit_customer_id", "=", line.customer_id]],
                    ["vehicle"]
                );
                line._vehicles = vehicles;
            }

        }
        // ✏️ SHIFT OPEN → LOAD FROM UI STATE
        else {
            if (!this.state.creditData[shiftId]) {
                this.state.creditData[shiftId] = [];
            }
            creditLines = (this.state.creditData[shiftId] || []).map(l => ({
                customer_id: l.customer_id || null,
                vehicle_no: l.vehicle_no || "",
                quantity: l.quantity || 0,
                amount: l.amount || 0,
                _vehicles: l._vehicles || [],
                _uid: l._uid || crypto.randomUUID(),
            }));
        }

        this.dialog.add(CreditDialog, {
            creditLines,
            readonly: record.state === "close",
            onSave: (lines) => {
                this.state.creditData[shiftId] = lines;
            },
        });
    }

    /* ============================================================================
       ⭐ LOYALTY: OPEN POPUP
    ============================================================================ */
    async openLoyaltyPopup(ev) {
        const shiftId = parseInt(ev.currentTarget.dataset.shift);
        const record = this.state.shift_manager.find(s => s.id === shiftId);
        if (!record) return;

        if (!this.state.loyaltyData[shiftId]) {
            this.state.loyaltyData[shiftId] = [];
        }

        const loyaltyLines = this.state.loyaltyData[shiftId].map(l => ({
            customer_id: l.customer_id || null,
            quantity: l.quantity || 0,
            use_reward: l.use_reward || false,
            selected_reward_id: l.selected_reward_id || null,
            available_rewards: l.available_rewards || [],
            _uid: l._uid || crypto.randomUUID(),
        }));

        this.dialog.add(LoyaltyDialog, {
            loyaltyLines,
            productId: record.fuel_id,
            readonly: record.state === "close",
            onSave: (lines) => {
                this.state.loyaltyData[shiftId] = lines;
            },
        });
    }

    /* ON CLICK SUBMIT */
    async onClickSubmit(ev) {

        console.log("========== SUBMIT SHIFT START ==========");

        const shift_id = parseInt(ev.target.dataset.shift);
        const record = this.state.shift_manager.find(s => s.id === shift_id);
        const currentUserId = this.env.services.user.id;

        if (!record)
            return this.notification.add("Shift record not found", { type: "warning" });

        if (record.prev_shift_warning)
            return this.notification.add(record.prev_shift_warning, { type: "danger" });

        const start_reading = parseFloat(record.start_reading || 0);
        const end_reading = parseFloat(record.end_reading || 0);

        if (!end_reading)
            return this.notification.add("End Reading is required.", { type: "warning" });

        if (end_reading < start_reading)
            return this.notification.add("End Reading cannot be less than Start Reading.", { type: "danger" });

        /* DIP TEST VALIDATION */
        if (record.dip_test) {

            const taken = parseFloat(record.dip_taken_qty || 0);
            const returned = parseFloat(record.dip_returned_qty || 0);

            if (returned < 0) {
                return this.notification.add(
                    "DIP Test: Returned quantity cannot be negative.",
                    { type: "warning" }
                );
            }

            if (returned > taken) {
                return this.notification.add(
                    "DIP Test: Returned quantity cannot exceed taken quantity.",
                    { type: "danger" }
                );
            }
        }

        /* TOTAL DISPENSED QTY */
        const totalQty = end_reading - start_reading;

        if (totalQty <= 0)
            return this.notification.add("Sale quantity must be greater than zero.", { type: "warning" });

        /* GET NOZZLE PRODUCT */
        const [nozzle] = await this.orm.searchRead(
            "fuel.station.nozzle",
            [["id", "=", record.nozzle_id]],
            ["product_id"]
        );

        const productId = nozzle?.product_id?.[0];

        if (!productId)
            return this.notification.add("No product linked to this nozzle.", { type: "danger" });

        const [product] = await this.orm.searchRead(
            "product.product",
            [["id", "=", productId]],
            ["list_price"]
        );

        const productPrice = parseFloat(product?.list_price || 0);

        console.log("Product Price : ",productPrice)

        /* GET NOZZLE NAME */
        const [nozzleRec] = await this.orm.searchRead(
            "fuel.station.nozzle",
            [["id", "=", record.nozzle_id]],
            ["name"]
        );
        const nozzleName = nozzleRec?.name || "Nozzle";

        const today = new Date();
        const formattedDate = today.toLocaleDateString("en-GB");
        // Example: 30/12/2025

        const paymentRefBase = `${nozzleName} | ${formattedDate}`;

        /* CREDIT QTY CALCULATION */
        const creditLines = this.state.creditData[record.id] || [];
        let totalCreditQty = 0;

        for (const line of creditLines) {
            const qty = parseFloat(line.quantity || 0);
            if (qty > 0) totalCreditQty += qty;
        }

        /* LOYALTY QTY CALCULATION */
        const loyaltyLines = this.state.loyaltyData[record.id] || [];
        let totalLoyaltyQty = 0;

        for (const line of loyaltyLines) {
            const qty = parseFloat(line.quantity || 0);
            if (qty > 0) totalLoyaltyQty += qty;
        }

        /* VALIDATION */
        if ((totalCreditQty + totalLoyaltyQty) > totalQty) {
            return this.notification.add(
                "Credit + Loyalty quantity cannot exceed total dispensed quantity.",
                { type: "danger" }
            );
        }

        let dipQty = 0;
        if (record.dip_test) {
            dipQty = parseFloat(record.dip_taken_qty || 0);
        }

        /* NET QTY FOR AMOUNT (LOYALTY INCLUDED ✅) */
        const netQty = totalQty - totalCreditQty - dipQty;

        console.log("netQty : ",netQty)

        /* CLOSE SHIFT */
        await this.orm.write("fuel.shift.manager", [record.id], {
            start_reading,
            end_reading,
            price: productPrice,
            dip_test:record.dip_test,
            dip_taken_qty:record.dip_taken_qty,
            dip_returned_qty:record.dip_returned_qty,
            state: "close",
        });

        /* WALK-IN QTY (FIXED ✅) */
        const walkInQty = totalQty - (totalCreditQty + totalLoyaltyQty);

        /* CREATE CLOSING ENTRY*/
        const [closingId] = await this.orm.create("closing.entry", [{
            pump_id: record.pump_id,
            shift_id: record.shift_id,
            shift_manager_id: record.id,
            nozzle_id: record.nozzle_id,
            employee_id: record.employee_id,
            dip_taken_qty:record.dip_taken_qty,
            dip_returned_qty:record.dip_returned_qty,
            price: productPrice,
            start_reading,
            end_reading,
        }]);

        /* WALK-IN SALE LINE */
        if (walkInQty > 0) {
            await this.orm.create("walkin.sale.line", [{
                closing_entry_id: closingId,
                quantity: walkInQty,
                price: productPrice,
            }]);
        }

        /* CREDIT SALE LINES*/
        for (const line of creditLines) {
            await this.orm.create("credit.sale.line", [{
                closing_entry_id: closingId,
                customer_id: line.customer_id,
                vehicle_no: line.vehicle_no,
                quantity: line.quantity,
                price: productPrice,
            }]);
        }
        for (const line of loyaltyLines) {
            await this.orm.create("closing.loyalty.line", [{
                closing_entry_id: closingId,
                customer_id: line.customer_id,
                quantity: line.quantity,
                price: productPrice,
            }]);
        }

        await this.loadShiftDetails();

        this.notification.add(
            "Meter Reading Submitted successfully!",
            { type: "success" }
        );
    }
}

/* ============================================================================
   CREDIT DIALOG (ISOLATED, DOES NOT AFFECT MAIN LOGIC)
============================================================================ */
export class CreditDialog extends Component {
    static template = "fuel_station.credit_dialog";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.readonly = this.props.readonly || false;

        this.lines = useState(
            (this.props.creditLines || []).map(l => ({
                customer_id: l.customer_id || null,
                vehicle_no: l.vehicle_no || "",
                quantity: l.quantity || 0,
                amount: l.amount || 0,
                _vehicles: l._vehicles || [],
                _uid: l._uid || crypto.randomUUID(),
            }))
        );

        this.customers = useState([]);

        this.loadCustomers();
        this.loadVehiclesForExistingLines();
    }

    /* ===============================
       LOAD CREDIT CUSTOMERS
    =============================== */
    async loadCustomers() {
        const res = await this.orm.searchRead(
            "res.partner",
            [["is_credit_customer", "=", true]],
            ["id", "name"]
        );
        this.customers.push(...res);
    }

    /* ===============================
       ON CUSTOMER CHANGE
    =============================== */
    async onCustomerChange(ev) {
        const index = parseInt(ev.currentTarget.dataset.index);
        const customerId = parseInt(ev.currentTarget.value);

        const line = this.lines[index];
        if (!line) return;

        line.customer_id = customerId;
        line.vehicle_no = "";
        line._vehicles = [];

        if (!customerId) return;

        const vehicles = await this.orm.searchRead(
            "credit.vehicle.line",
            [["credit_customer_id", "=", customerId]],
            ["vehicle"]
        );

        line._vehicles = vehicles;
    }

    /* ===============================
       LOAD VEHICLES FOR EXISTING LINES
    =============================== */
    async loadVehiclesForExistingLines() {
        for (const line of this.lines) {
            if (!line.customer_id) continue;

            const vehicles = await this.orm.searchRead(
                "credit.vehicle.line",
                [["credit_customer_id", "=", line.customer_id]],
                ["vehicle"]
            );

            line._vehicles = vehicles;
        }
    }

    /* ===============================
       ADD / REMOVE LINES
    =============================== */
    addLine() {
        this.lines.push({
            customer_id: null,
            vehicle_no: "",
            quantity: 0,
            amount: 0,
            _vehicles: [],
            _uid: crypto.randomUUID(),
        });
    }

    removeLine(ev) {
        this.lines.splice(parseInt(ev.currentTarget.dataset.index), 1);
    }

    /* ===============================
       SAVE + AUTO CREATE VEHICLE
    =============================== */
    async save() {
        for (const line of this.lines) {
            if (!line.customer_id || !line.vehicle_no) continue;

            // Normalize vehicle number
            const vehicle = line.vehicle_no.trim().toUpperCase();
            line.vehicle_no = vehicle;

            const existing = await this.orm.searchCount(
                "credit.vehicle.line",
                [
                    ["credit_customer_id", "=", line.customer_id],
                    ["vehicle", "=", vehicle],
                ]
            );

            if (existing === 0) {
                await this.orm.create("credit.vehicle.line", [{
                    credit_customer_id: line.customer_id,
                    vehicle: vehicle,
                }]);
            }
        }

        this.props.onSave(this.lines);
        this.props.close();
    }
}


/* ============================================================================
   LOYALTY DIALOG
============================================================================ */
export class LoyaltyDialog extends Component {
    static template = "fuel_station.loyalty_dialog";
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.readonly = this.props.readonly || false;
        this.productId = this.props.productId;

        this.lines = useState(
            (this.props.loyaltyLines || []).map(l => ({
                customer_id: l.customer_id || null,
                quantity: l.quantity || 0,
                use_reward: l.use_reward || false,
                selected_reward_id: l.selected_reward_id || null,
                available_rewards: l.available_rewards || [],
                _uid: l._uid || crypto.randomUUID(),
            }))
        );

        this.customers = useState([]);
        this.loadCustomers();
    }

    async loadCustomers() {
        const res = await this.orm.searchRead(
            "res.partner",
            [["is_loyalty_customer", "=", true]], // ⭐ FILTER
            ["id", "name"]
        );
        this.customers.push(...res);
    }

    async onRewardToggle(ev) {
        const index = parseInt(ev.currentTarget.dataset.index);
        const checked = ev.currentTarget.checked;

        const line = this.lines[index];
        if (!line) return;

        line.use_reward = checked;
        line.selected_reward_id = null;
        line.available_rewards = [];

        if (!checked) return;

        if (!line.customer_id || !line.quantity) {
            this.notification.add(
                "Select customer and quantity first.",
                { type: "warning" }
            );
            line.use_reward = false;
            return;
        }

        // 🔥 CALL BACKEND
        const rewards = await this.orm.call(
            "sale.order",
            "get_loyalty_claimable_rewards",
            [
                line.customer_id,
                this.props.productId,   // 🔴 IMPORTANT (see note below)
                line.quantity,
            ]
        );

        if (!rewards.length) {
            this.notification.add(
                "No rewards available for this customer.",
                { type: "info" }
            );
            line.use_reward = false;
            return;
        }

        line.available_rewards = rewards;
    }


    async onCustomerChange(ev) {
        const index = parseInt(ev.currentTarget.dataset.index);
        const customerId = parseInt(ev.currentTarget.value);

        const line = this.lines[index];
        if (!line) return;

        line.customer_id = customerId;

        // 🔁 Reset reward selection when customer changes
        line.use_reward = false;
        line.selected_reward_id = null;
        line.available_rewards = [];
    }


    addLine() {
        this.lines.push({
            customer_id: null,
            quantity: 0,
            use_reward: false,
            selected_reward_id: null,
            available_rewards: [],
            _uid: crypto.randomUUID(),
        });
    }

    removeLine(ev) {
        this.lines.splice(parseInt(ev.currentTarget.dataset.index), 1);
    }

    save() {
        for (const l of this.lines) {
            l.selected_reward_id = l.selected_reward_id
                ? parseInt(l.selected_reward_id)
                : null;
        }
        this.props.onSave(this.lines);
        this.props.close();
    }

}

registry.category("actions").add("fuel_station.user_screen", UserScreen);
