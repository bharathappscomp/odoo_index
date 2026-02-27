/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatCurrency } from "@web/core/currency";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";


export class FuelDashboard extends Component {
    static template = "fuel_station.fuel_dashboard_main";
    formatCurrency = formatCurrency;


    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");



        const today = new Date().toISOString().slice(0, 10);

        this.state = useState({
            nozzlesFlat: [],
            shifts: [],
            employees: [],
            selections: {},
            assignedCells: {},
            loading: false,
            assign_date: today,
            recent_closings: [],
            products_stock: [],
             // Shift Based Collection
            collection: [],
            collection_page: 1,
            collection_page_size: 5,
            from_date: today,
            to_date: today,
            group_by: "shift",
            sortOrder: "asc",
            shiftSortOrder: "asc",
            pricing_date: today,
            fuel_pricing: [],
            fuel_sales: [],
            fuel_sale_type: "all",   // all | walk | credit | loyalty
            page: 1,
            pageSize: 5,
            hasNext: false,
            hasPrev: false,
            credit_invoices: [],
            credit_loading: false,
            credit_page: 1,
            credit_page_size: 5,
            credit_hasNext: false,
            credit_hasPrev: false,
            customer_wise: false,
            today_sales_amount: 0,
            today_sales_loading: false,
            currentStockIndex: 0,
            tilesPerPage: 5,
        });

        onMounted(async () => {
            await this.loadAll();
            await this.loadAssignmentsForDate();
            await this.loadRecentClosings();
            await this.loadStockProducts();
            await this.loadFuelPricing();
            await this.loadFuelSales();
            await this.loadCollection();
            this.state.credit_page = 1;
            await this.loadCreditInvoices();
            await this.loadTodaySalesAmount();

            const grids = document.querySelectorAll(".stock-grid-top");

            grids.forEach(grid => {
                grid.addEventListener(
                    "wheel",
                    (ev) => {
                        if (Math.abs(ev.deltaY) > Math.abs(ev.deltaX)) {
                            ev.preventDefault();
                            grid.scrollLeft += ev.deltaY;
                        }
                    },
                    { passive: false }
                );
            });

        });
    }

    get visibleStocks() {
        const { currentStockIndex, tilesPerPage } = this.state;
        return this.state.products_stock.slice(
            currentStockIndex,
            currentStockIndex + tilesPerPage
        );
    }

    nextStock() {
        const maxIndex =
            this.state.products_stock.length - this.state.tilesPerPage;

        if (this.state.currentStockIndex < maxIndex) {
            this.state.currentStockIndex += this.state.tilesPerPage;
        }
    }

    prevStock() {
        if (this.state.currentStockIndex > 0) {
            this.state.currentStockIndex -= this.state.tilesPerPage;
        }
    }

    openReassignDialog() {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirm Reassignment"),
                body: _t("An assignment already exists for this nozzle and shift.\nContinuing will update the employee if the shift is open, or create a new assignment if it is closed.\nDo you want to proceed?"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                confirmLabel: _t("Reassign"),
                cancelLabel: _t("Cancel"),
            });
        });
    }

    sortByColumn(field) {
        if (this.state.sortBy === field) {
            this.state.sortOrder =
                this.state.sortOrder === "asc" ? "desc" : "asc";
        } else {
            this.state.sortBy = field;
            this.state.sortOrder = "asc";
        }

        const order = this.state.sortOrder === "asc" ? 1 : -1;

        this.state.recent_closings.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            // many2one
            if (Array.isArray(valA)) valA = valA[1];
            if (Array.isArray(valB)) valB = valB[1];

            // null safety
            if (valA == null) return -1 * order;
            if (valB == null) return 1 * order;

            // number
            if (typeof valA === "number") {
                return (valA - valB) * order;
            }

            // date
            if (!isNaN(Date.parse(valA))) {
                return (new Date(valA) - new Date(valB)) * order;
            }

            // string
            return valA.toString().localeCompare(valB.toString()) * order;
        });
    }

    async loadCreditInvoices() {
        this.state.credit_loading = true;

        try {
            const offset =
                (this.state.credit_page - 1) * this.state.credit_page_size;

            // fetch one extra to detect next page
            const records = await this.orm.searchRead(
                "account.move",
                [
                    ["move_type", "=", "out_invoice"],
                    ["fuel_inv_type", "=", "credit"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["state", "=", "posted"],
                ],
                [
                    "name",
                    "invoice_date",
                    "partner_id",
                    "amount_total",
                    "amount_residual_signed",
                    "payment_state",
                ],
                {
                    order: "invoice_date desc",
                    limit: this.state.credit_page_size + 1,
                    offset: offset,
                }
            );

            this.state.credit_hasPrev = this.state.credit_page > 1;
            this.state.credit_hasNext =
                records.length > this.state.credit_page_size;

            // keep only page size
            this.state.credit_invoices = records.slice(
                0,
                this.state.credit_page_size
            );
        } finally {
            this.state.credit_loading = false;
        }
    }

    onCreditNextPage() {
        if (!this.state.credit_hasNext) return;
        this.state.credit_page += 1;
        this.loadCreditInvoices();
    }

    onCreditPrevPage() {
        if (!this.state.credit_hasPrev) return;
        this.state.credit_page -= 1;
        this.loadCreditInvoices();
    }

    get customerWiseInvoices() {
        const result = {};

        for (const inv of this.state.credit_invoices) {
            if (!inv.partner_id) continue;

            const partnerId = inv.partner_id[0];
            const partnerName = inv.partner_id[1];

            if (!result[partnerId]) {
                result[partnerId] = {
                    partner_id: partnerId,
                    partner_name: partnerName,
                    total_amount: 0,
                    due_amount: 0,
                };
            }

            result[partnerId].total_amount += inv.amount_total || 0;
            result[partnerId].due_amount += inv.amount_residual_signed || 0;
        }

        return Object.values(result);
    }

    toggleCustomerWise(ev) {
        this.state.customer_wise = ev.target.checked;
    }

    get totalUnpaidCreditDue() {
        return this.state.credit_invoices.reduce(
            (sum, inv) => sum + (inv.amount_residual_signed || 0),
            0
        );
    }

    async loadTodaySalesAmount() {
        this.state.today_sales_loading = true;

        try {
            const today = new Date().toISOString().slice(0, 10);

            const orders = await this.orm.searchRead(
                "sale.order",
                [
                    ["state", "in", ["sale"]],
                    ["is_fuel_sale", "=", true],
                    ["date_order", ">=", today + " 00:00:00"],
                    ["date_order", "<=", today + " 23:59:59"],
                ],
                ["amount_total"]
            );

            this.state.today_sales_amount = orders.reduce(
                (sum, o) => sum + (o.amount_total || 0),
                0
            );
        } finally {
            this.state.today_sales_loading = false;
        }
    }

    getSortIcon(field) {
        if (this.state.sortBy !== field) return "";
        return this.state.sortOrder === "asc" ? "▲" : "▼";
    }

    sortShiftCollection(field) {
        if (this.state.shiftSortBy === field) {
            this.state.shiftSortOrder =
                this.state.shiftSortOrder === "asc" ? "desc" : "asc";
        } else {
            this.state.shiftSortBy = field;
            this.state.shiftSortOrder = "asc";
        }

        const order = this.state.shiftSortOrder === "asc" ? 1 : -1;

        this.state.shift_collection.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            if (valA == null) return -1 * order;
            if (valB == null) return 1 * order;

            // number sorting
            if (typeof valA === "number") {
                return (valA - valB) * order;
            }

            // string sorting
            return valA.toString().localeCompare(valB.toString()) * order;
        });
    }

    getShiftSortIcon(field) {
        if (this.state.shiftSortBy !== field) return "";
        return this.state.shiftSortOrder === "asc" ? "▲" : "▼";
    }


    async loadFuelPricing() {
        // 1️⃣ Find latest pricing record <= selected date
        const pricingRecords = await this.orm.searchRead(
            "fuel.pricing",
            [["pricing_date", "<=", this.state.pricing_date]],
            ["id", "pricing_date", "line_ids"],
            {
                order: "pricing_date desc",
                limit: 1,
            }
        );

        if (!pricingRecords.length) {
            this.state.fuel_pricing = [];
            return;
        }

        const pricing = pricingRecords[0];

        // 2️⃣ Fetch pricing lines
        const lines = await this.orm.searchRead(
            "fuel.pricing.line",
            [["pricing_id", "=", pricing.id]],
            ["product_id", "price"]
        );

        // 3️⃣ Prepare UI data
        this.state.fuel_pricing = lines.map(l => ({
            product_name: l.product_id?.[1],
            price: l.price,
        }));
    }

    onPricingDateChange(ev) {
        this.state.pricing_date = ev.target.value;
        this.loadFuelPricing();
    }

    async loadFuelSales() {
        const domain = [["is_fuel_sale", "=", true]];

        if (this.state.fuel_sale_type !== "all") {
            domain.push(["fuel_sale_type", "=", this.state.fuel_sale_type]);
        }

        const offset = (this.state.page - 1) * this.state.pageSize;

        // Fetch 1 extra record to check next page
        const records = await this.orm.searchRead(
            "sale.order",
            domain,
            [
                "name",
                "date_order",
                "partner_id",
                "fuel_sale_type",
                "amount_total",
                "order_line",
            ],
            {
                order: "date_order desc",
                limit: this.state.pageSize + 1,
                offset: offset,
            }
        );

        for (const rec of records) {
            rec.product_name = "-";
            rec.quantity = 0;

            if (rec.order_line && rec.order_line.length) {
                const [line] = await this.orm.searchRead(
                    "sale.order.line",
                    [["id", "=", rec.order_line[0]]],
                    ["product_id", "product_uom_qty"]
                );

                if (line) {
                    rec.product_name = line.product_id?.[1] || "-";
                    rec.quantity = line.product_uom_qty || 0;
                }
            }
        }


        this.state.hasPrev = this.state.page > 1;
        this.state.hasNext = records.length > this.state.pageSize;

        // keep only 5 rows
        this.state.fuel_sales = records.slice(0, this.state.pageSize);
    }

    onFuelSaleTypeChange(ev) {
        this.state.fuel_sale_type = ev.target.value;
        this.state.page = 1;
        this.loadFuelSales();
    }

    onNextPage() {
        if (!this.state.hasNext) return;
        this.state.page += 1;
        this.loadFuelSales();
    }

    onPrevPage() {
        if (!this.state.hasPrev) return;
        this.state.page -= 1;
        this.loadFuelSales();
    }

    async loadStockProducts() {

        // 1️⃣ Fetch stock
        const quants = await this.orm.searchRead(
            "stock.quant",
            [
                ["product_id.is_fuel_product", "=", true],
                ["product_id.active", "=", true],
                ["location_id.usage", "=", "internal"],
            ],
            ["product_id", "location_id", "quantity", "product_uom_id"]
        );

        // 2️⃣ Collect unique product IDs
        const productIds = [...new Set(quants.map(q => q.product_id[0]))];

        // 3️⃣ Fetch product prices
        const products = await this.orm.searchRead(
            "product.product",
            [["id", "in", productIds]],
            ["id", "list_price", "currency_id"]
        );

        // 4️⃣ Create price lookup
        const priceMap = {};
        products.forEach(p => {
            priceMap[p.id] = {
                price: p.list_price,
                currency: p.currency_id?.[1] || "-",
            };
        });

        // 5️⃣ Merge stock + price
        this.state.products_stock = quants.map(q => ({
            id: `${q.product_id[0]}_${q.location_id[0]}`,
            product_id: q.product_id[0],
            product_name: q.product_id[1],
            location_id: q.location_id[0],
            location_name: q.location_id[1],
            qty: q.quantity,
            uom: q.product_uom_id?.[1] || "",
            price: priceMap[q.product_id[0]]?.price || 0,
            currency: priceMap[q.product_id[0]]?.currency || "-",
            stock_value: q.quantity * (priceMap[q.product_id[0]]?.price || 0),

        }));
    }


    getProductImageUrl(productId) {
        return `/web/image/product.product/${productId}/image_128`;
    }

    async loadAll() {
        this.state.loading = true;

        try {
            await Promise.all([
                this.loadShifts(),
                this.loadNozzles(),
                this.loadEmployees()
            ]);

            this.state.nozzlesFlat.sort((a, b) => {
                if (a.pump_name < b.pump_name) return -1;
                if (a.pump_name > b.pump_name) return 1;
                return a.name.localeCompare(b.name);
            });

        } finally {
            this.state.loading = false;
        }
    }

    async loadShifts() {
        this.state.shifts = await this.orm.searchRead(
            "fuel.station.shift",
            [],
            ["name", "start_time", "end_time"]
        );
    }

    async loadNozzles() {
        const nozzles = await this.orm.searchRead(
            "fuel.station.nozzle",
            [],
            ["name", "pump_id", "product_id"]
        );

        this.state.nozzlesFlat = nozzles.map(n => ({
            id: n.id,
            name: n.name,
            pump_id: n.pump_id?.[0] || null,
            pump_name: n.pump_id?.[1] || "",
        }));
    }

    async loadEmployees() {
        this.state.employees = await this.orm.searchRead(
            "hr.employee",
            [],
            ["name"]
        );
    }

    async loadRecentClosings() {
        this.state.recent_closings = await this.orm.searchRead(
            "closing.entry",
            [],
            ["create_date","shift_id","pump_id","nozzle_id","start_reading","end_reading","opening_amount","closing_amount","employee_id","fuel_id"],
            { limit: 5, order: "create_date desc" }
        );
    }

    async onSelectEmployee(shiftId, nozzleId, ev) {
        const empId = Number(ev.target.value);

        const alreadyAssigned =
            this.state.assignedCells[shiftId] &&
            this.state.assignedCells[shiftId][nozzleId];

        if (alreadyAssigned) {
            const confirmed = await this.openReassignDialog();

            if (!confirmed) {
                ev.target.value = this.getSelected(shiftId, nozzleId);
                return;
            }

            await this.updateAssignment(shiftId, nozzleId, empId);
            await this.loadAssignmentsForDate();

            this.notification.add(_t("Employee reassigned successfully."), {
                type: "success",
            });
            return;
        }

        if (!this.state.selections[shiftId]) {
            this.state.selections[shiftId] = {};
        }

        this.state.selections[shiftId][nozzleId] = empId;
    }

    getSelected(shiftId, nozzleId) {
        return this.state.selections[shiftId]?.[nozzleId] || "";
    }

    async updateAssignment(shiftId, nozzleId, empId) {
        const date = this.state.assign_date;

        console.group("🔄 updateAssignment");
        console.log("Input →", { shiftId, nozzleId, empId, date });

        const rec = await this.orm.searchRead(
            "fuel.shift.manager",
            [
                ["shift_id", "=", shiftId],
                ["nozzle_id", "=", nozzleId],
                ["assigned_date", "=", date],
            ],
            ["id", "state", "pump_id"]
        );

        console.log("Search result →", rec);

        if (rec.length) {
            const record = rec[0];

            if (record.state === "close") {
                console.warn("Shift CLOSED → creating new record");

                await this.orm.create("fuel.shift.manager", [
                    {
                        shift_id: shiftId,
                        nozzle_id: nozzleId,
                        pump_id: record.pump_id?.[0],
                        employee_id: empId,
                        assigned_date: date,
                        reassigned_after_closing: true,
                        state: "open",
                    }
                ]);

                console.log("✅ New record created after closing");
            } else {
                console.info("Shift OPEN → updating existing record");

                await this.orm.write(
                    "fuel.shift.manager",
                    [record.id],
                    {
                        employee_id: empId,
                        reassigned_before_closing: true,
                    }
                );

                console.log("✅ Existing record updated", record.id);
            }
        } else {
            console.warn("No record found → creating fresh assignment");

            await this.orm.create("fuel.shift.manager", [
                {
                    shift_id: shiftId,
                    nozzle_id: nozzleId,
                    employee_id: empId,
                    assigned_date: date,
                    state: "open",
                }
            ]);

            console.log("✅ Fresh record created");
        }

        console.groupEnd();
    }

    getReadableAssignments() {
        const result = [];

        for (const shiftId in this.state.selections) {
            for (const nozzleId in this.state.selections[shiftId]) {

                if (this.state.assignedCells[shiftId]?.[nozzleId]) continue;

                const empId = Number(this.state.selections[shiftId][nozzleId]);
                const nozzle = this.state.nozzlesFlat.find(n => n.id == nozzleId);
                const employee = this.state.employees.find(e => e.id == empId);

                result.push({
                    shift_id: Number(shiftId),
                    employee_id: employee.id,
                    pump_id: nozzle.pump_id,
                    nozzle_id: nozzle.id,
                });
            }
        }
        return result;
    }

    async onAssignClick() {
        const assignments = this.getReadableAssignments();
        if (!assignments.length) {
            this.notification.add(_t("No employees selected."), { type: "warning" });
            return;
        }

        const date = this.state.assign_date;
        if (!date) {
            this.notification.add(_t("Please select an assignment date."), {
                type: "warning",
            });
            return;
        }

        // ✅ DATE ONLY comparison (no hours involved)
        const todayStr = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

        if (date < todayStr) {
            this.notification.add(
                _t("You cannot assign shifts for past dates."),
                { type: "danger" }
            );
            return;
        }

        // ✅ Create records
        for (const row of assignments) {
            await this.orm.create("fuel.shift.manager", [{
                ...row,
                assigned_date: date,
            }]);
        }

        this.notification.add(_t("Assignments saved successfully."), {
            type: "success",
        });

        await this.loadAssignmentsForDate();
        await this.loadRecentClosings();
    }

    async onDateChange() {
        await this.loadAssignmentsForDate();
    }

    async loadAssignmentsForDate() {
        this.state.selections = {};
        this.state.assignedCells = {};

        const date = this.state.assign_date;

        const items = await this.orm.searchRead(
            "fuel.shift.manager",
            [["assigned_date", "=", date]],
            ["shift_id", "employee_id", "nozzle_id"]
        );

        for (const rec of items) {
            const shiftId = rec.shift_id[0];
            const nozzleId = rec.nozzle_id[0];
            const empId = rec.employee_id[0];

            if (!this.state.selections[shiftId]) {
                this.state.selections[shiftId] = {};
            }
            this.state.selections[shiftId][nozzleId] = empId;

            if (!this.state.assignedCells[shiftId]) {
                this.state.assignedCells[shiftId] = {};
            }
            this.state.assignedCells[shiftId][nozzleId] = true;
        }
    }


    /* ================= BASED COLLECTION ================= */

    async loadCollection() {
        const { from_date, to_date, group_by } = this.state;
        if (!from_date || !to_date) return;

        // reset ONLY collection pagination
        this.state.collection_page = 1;

        const closings = await this.orm.searchRead(
            "closing.entry",
            [
                ["create_date", ">=", from_date + " 00:00:00"],
                ["create_date", "<=", to_date + " 23:59:59"],
            ],
            [
                "shift_id",
                "nozzle_id",
                "pump_id",
                "start_reading",
                "end_reading",
            ]
        );

        const fieldMap = {
            shift: "shift_id",
            nozzle: "nozzle_id",
            pump: "pump_id",
        };

        const field = fieldMap[group_by];
        const result = {};

        for (const c of closings) {
            if (!c[field]) continue;

            const id = c[field][0];
            const name = c[field][1];
            const qty = (c.end_reading || 0) - (c.start_reading || 0);

            if (!result[id]) {
                result[id] = {
                    name,
                    total_sales: 0,
                };
            }

            result[id].total_sales += qty;
        }

        this.state.collection = Object.values(result);
    }

    // ===============================
    // GROUP BY TOGGLE
    // ===============================
    setGroupBy(type) {
        this.state.group_by = type;
        this.loadCollection();
    }

    onCollectionDateChange() {
        const today = new Date().toISOString().slice(0, 10);

        if (this.state.from_date > today || this.state.to_date > today) {
            this.notification.add("Future dates are not allowed", { type: "warning" });
            return;
        }

        if (this.state.from_date > this.state.to_date) {
            this.notification.add("From date cannot be after To date", { type: "warning" });
            return;
        }

        this.state.collection_page = 1;
        this.loadCollection();
    }



    // ===============================
    // PAGINATION
    // ===============================
    get paginatedRows() {
        if (!Array.isArray(this.state.collection)) {
            return [];
        }
        const start =
            (this.state.collection_page - 1) * this.state.collection_page_size;

        return this.state.collection.slice(
            start,
            start + this.state.collection_page_size
        );
    }

    nextPage() {
        if (
            this.state.collection_page * this.state.collection_page_size <
            this.state.collection.length
        ) {
            this.state.collection_page++;
        }
    }

    prevPage() {
        if (this.state.collection_page > 1) {
            this.state.collection_page--;
        }
    }


    onClickClose() {
        this.env.services.action.doAction("fuel_station.action_closing_entry");
    }
}

registry.category("actions").add("fuel_station.fuel_dashboard_main", FuelDashboard);
