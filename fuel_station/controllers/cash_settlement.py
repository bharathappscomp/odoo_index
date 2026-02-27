from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

class ClosingEntry(models.Model):
    _inherit = "closing.entry"

    @api.model
    def get_cash_settlement_entries(self, filters):
        domain = []

        # --------------------------------------------------
        # 🔐 EMPLOYEE RESOLUTION (ADMIN OVERRIDE SAFE)
        # --------------------------------------------------
        employee = None
        employee_id = filters.get("employee_id")

        # Admin can choose employee
        if (
                employee_id
                and self.env.user.has_group("fuel_station.group_fuel_admin")
        ):
            employee = self.env["hr.employee"].browse(employee_id)

        # Fallback: logged-in user employee
        if not employee:
            employee = self.env.user.employee_id

        if not employee:
            return []

        petty_cash = employee.petty_cash_balance or 0.0

        domain.append(("employee_id", "=", employee.id))

        # ✅ ONLY OPEN CLOSING ENTRIES
        domain.append(("state", "=", "open"))

        # 📅 Date filter
        date = filters.get("date")
        if date:
            domain += [
                ("create_date", ">=", f"{date} 00:00:00"),
                ("create_date", "<=", f"{date} 23:59:59"),
            ]

        # Optional filters
        if filters.get("shift_ids"):
            domain.append(("shift_id", "in", filters["shift_ids"]))

        if filters.get("pump_ids"):
            domain.append(("pump_id", "in", filters["pump_ids"]))

        if filters.get("nozzle_ids"):
            domain.append(("nozzle_id", "in", filters["nozzle_ids"]))

        entries = self.search(domain)

        # ======================================================
        # 🔥 CONSOLIDATION LOGIC
        # ======================================================

        result = {}

        for entry in entries:
            shift = entry.shift_id
            fuel = entry.fuel_id
            price = entry.price

            if not shift or not fuel or not price:
                continue

            # -------------------------
            # SHIFT LEVEL
            # -------------------------
            if shift.id not in result:
                result[shift.id] = {
                    "shift_id": shift.id,
                    "shift_name": shift.name,
                    "date": date,
                    "rows": {},
                    "shift_total": 0.0,
                    "closing_entry_ids": set(),
                }

            shift_data = result[shift.id]

            shift_data["closing_entry_ids"].add(entry.id)

            # -------------------------
            # FUEL + PRICE LEVEL
            # -------------------------
            key = (fuel.id, price)

            if key not in shift_data["rows"]:
                shift_data["rows"][key] = {
                    "fuel_id": fuel.id,
                    "fuel_name": fuel.display_name,
                    "price": price,

                    "pumps": set(),
                    "nozzles": set(),

                    "walkin_qty": 0.0,
                    "walkin_amount": 0.0,

                    "dip_qty": 0.0,
                    "dip_amount": 0.0,

                    "credit_qty": 0.0,
                    "credit_amount": 0.0,

                    "loyalty_qty": 0.0,
                    "loyalty_amount": 0.0,

                    "row_total": 0.0,
                }

            row = shift_data["rows"][key]

            # Track pumps & nozzles
            if entry.pump_id:
                row["pumps"].add(entry.pump_id.name)
            if entry.nozzle_id:
                row["nozzles"].add(entry.nozzle_id.name)

            # -------------------------
            # DIP ADJUSTMENT (SOURCE ONLY)
            # -------------------------
            if entry.dip_taken_qty:
                row["dip_qty"] += entry.dip_taken_qty
                row["dip_amount"] += entry.dip_taken_qty * entry.price

            # -------------------------
            # WALK-IN SALES
            # -------------------------
            for line in entry.walkin_ids:
                row["walkin_qty"] += line.quantity or 0.0
                row["walkin_amount"] += line.amount or 0.0

            # FRONTEND-ONLY DIP ADJUSTMENT
            if entry.dip_taken_qty:
                row["walkin_qty"] -= entry.dip_taken_qty
                row["walkin_amount"] -= entry.dip_taken_qty * entry.price

            # -------------------------
            # CREDIT SALES
            # -------------------------
            for line in entry.credit_ids:
                row["credit_qty"] += line.quantity or 0.0
                row["credit_amount"] += line.amount or 0.0

            # -------------------------
            # LOYALTY SALES
            # -------------------------
            for line in entry.loyalty_line_ids:
                row["loyalty_qty"] += line.quantity or 0.0
                row["loyalty_amount"] += line.amount or 0.0

            # -------------------------
            # TOTAL SALE (SOURCE OF TRUTH)
            # -------------------------
            row["row_total"] += entry.total_sale_amount or 0.0

        # ======================================================
        # 🔢 FINALIZE TOTALS & SERIALIZE
        # ======================================================

        output = []

        for shift_data in result.values():
            rows = []
            shift_total = 0.0

            for row in shift_data["rows"].values():
                row_total = row["row_total"]

                shift_total += row_total

                rows.append({
                    "fuel_id": row["fuel_id"],
                    "fuel_name": row["fuel_name"],
                    "price": row["price"],

                    "pumps": list(row["pumps"]),
                    "nozzles": list(row["nozzles"]),

                    "walkin_qty": row["walkin_qty"],
                    "walkin_amount": row["walkin_amount"],

                    "credit_qty": row["credit_qty"],
                    "credit_amount": row["credit_amount"],

                    "loyalty_qty": row["loyalty_qty"],
                    "loyalty_amount": row["loyalty_amount"],

                    "dip_qty": row["dip_qty"],
                    "dip_amount": row["dip_amount"],

                    "row_total": row_total,
                })

            output.append({
                "shift_id": shift_data["shift_id"],
                "shift_name": shift_data["shift_name"],
                "date": shift_data["date"],
                "rows": rows,
                "petty_cash_balance": petty_cash,
                "expected_amount": shift_total + petty_cash,
                "shift_total": shift_total,
                "closing_entry_ids": list(shift_data["closing_entry_ids"]),
            })

        return output

    @api.model
    def action_submit_cash_settlement(self, payload):

        print("\n================ CASH SETTLEMENT START ================\n")
        print("Payload received:", payload)

        # ------------------------------------------------
        # EMPLOYEE RESOLUTION (ADMIN SAFE)
        # ------------------------------------------------
        employee = None
        employee_id = payload.get("employee_id")

        # Admin can submit for others
        if (
                employee_id
                and self.env.user.has_group("fuel_station.group_fuel_admin")
        ):
            employee = self.env["hr.employee"].browse(employee_id)

        # Fallback: logged-in user
        if not employee:
            employee = self.env.user.employee_id

        if not employee:
            raise ValidationError(_("No employee resolved for settlement."))

        if not employee:
            raise ValidationError(_("No employee linked to this user."))

        employee_account = employee.coa_id
        if not employee_account:
            raise ValidationError(_("Employee COA not configured."))

        print("Employee:", employee.name)
        print("Employee COA:", employee_account.code)

        # ------------------------------------------------
        # CLOSING ENTRIES
        # ------------------------------------------------
        closing_entries = self.search([
            ("id", "in", payload["closing_entry_ids"]),
            ("state", "!=", "settled"),
        ])

        if not closing_entries:
            raise ValidationError(_("No valid closing entries found."))

        shift_total = sum(closing_entries.mapped("total_sale_amount"))

        print("Closing Entries:", closing_entries.ids)
        print("Shift Total (Sales):", shift_total)

        # ------------------------------------------------
        # CREATE SETTLEMENT
        # ------------------------------------------------
        settlement = self.env["cash.settlement"].create({
            "employee_id": employee.id,
            "shift_id": payload["shift_id"],
            "date": payload["date"],
            "expected_amount": shift_total,
            "closing_entry_ids": [(6, 0, closing_entries.ids)],
        })

        print("Cash Settlement Created:", settlement.id)


        # ------------------------------------------------
        # PAYMENT TOTALS
        # ------------------------------------------------
        cash_submitted_total = 0.0
        bank_submitted_total = 0.0

        cash_journal = self.env["account.journal"].search(
            [("type", "=", "cash")], limit=1
        )
        if not cash_journal or not cash_journal.default_account_id:
            raise ValidationError(_("Cash journal/account not configured."))

        print("Cash Journal:", cash_journal.name)

        for line in payload["payment_lines"]:
            amount = line.get("amount", 0.0)
            journal_id = int(line["journal_id"])

            if journal_id == cash_journal.id:
                cash_submitted_total += amount
            else:
                bank_submitted_total += amount

        print("Cash Submitted Total :", cash_submitted_total)
        print("Bank Submitted Total :", bank_submitted_total)
        print("Total Submitted      :", cash_submitted_total + bank_submitted_total)

        # ------------------------------------------------
        # CORE LOGIC
        # ------------------------------------------------
        remaining_after_bank = max(shift_total - bank_submitted_total, 0.0)
        petty_cash_amount = max(cash_submitted_total - remaining_after_bank, 0.0)
        shortage_amount = max(shift_total - (bank_submitted_total + cash_submitted_total), 0.0)
        shift_cash_amount = cash_submitted_total - petty_cash_amount


        print("\n--- CALCULATION BREAKDOWN ---")
        print("Remaining after bank :", remaining_after_bank)
        print("Shift Cash Amount    :", shift_cash_amount)
        print("Petty Cash Amount    :", petty_cash_amount)
        print("Shortage Amount      :", shortage_amount)


        # ------------------------------------------------
        # PAYMENT LINES
        # ------------------------------------------------
        PaymentLine = self.env["cash.settlement.payment.line"]

        for line in payload["payment_lines"]:
            journal_id = int(line["journal_id"])
            amount = line["amount"]

            # BANK → unchanged
            if journal_id != cash_journal.id:
                PaymentLine.create({
                    "cash_settlement_id": settlement.id,
                    "journal_id": journal_id,
                    "ref": f"Shift {payload['shift_id']} | {payload['date']}",
                    "amount": amount,
                    "payment_type": "shift",
                })

            # CASH → SPLIT into shift + petty
            else:
                if shift_cash_amount > 0:
                    PaymentLine.create({
                        "cash_settlement_id": settlement.id,
                        "journal_id": cash_journal.id,
                        "ref": f"Shift {payload['shift_id']} | {payload['date']}",
                        "amount": shift_cash_amount,
                        "payment_type": "shift",
                    })

                if petty_cash_amount > 0:
                    PaymentLine.create({
                        "cash_settlement_id": settlement.id,
                        "journal_id": cash_journal.id,
                        "ref": f"Shift {payload['shift_id']} | {payload['date']} | Petty Cash Adjustment",
                        "amount": petty_cash_amount,
                        "payment_type": "petty_cash",
                    })

        print("Payment lines saved")

        # ------------------------------------------------
        # ACCOUNT MOVE
        # ------------------------------------------------
        debit_account = credit_account = False
        debit = credit = 0.0
        label = move_type = False

        cash_account = cash_journal.default_account_id
        company = cash_journal.company_id
        default_customer = self.env['res.partner'].search([('is_default_customer', '=', True)])

        if petty_cash_amount > 0:
            print(">> Creating PETTY CASH entry")

            debit_account = cash_account.id
            credit_account = employee_account.id
            debit = credit = petty_cash_amount
            label = "Petty Cash Adjustment"
            move_type = "petty_return"

        elif shortage_amount > 0:
            print(">> Creating SHORTAGE (DEBIT NOTE) entry")

            debit_account = employee_account.id
            credit_account = cash_account.id
            debit = credit = shortage_amount
            label = "Shift Shortage"
            move_type = "shortage"

        else:
            print(">> No accounting entry required (perfect settlement)")

        if debit_account and credit_account:
            move = self.env["account.move"].create({
                "journal_id": cash_journal.id,
                "company_id": company.id,
                "date": payload["date"],
                "ref": f"Cash Settlement | Shift {payload['shift_id']}",
                "move_type": "entry",
                "line_ids": [
                    (0, 0, {
                        "account_id": debit_account,
                        "debit": debit,
                        "credit": 0.0,
                        "name": label,
                    }),
                    (0, 0, {
                        "account_id": credit_account,
                        "debit": 0.0,
                        "credit": credit,
                        "name": label,
                    }),
                ],
            })

            move.action_post()

            self.env["cash.settlement.move"].create({
                "cash_settlement_id": settlement.id,
                "move_id": move.id,
                "move_type": move_type,
            })

            print("Account Move Posted:", move.id)

        # ------------------------------------------------
        # AUDIT LINES
        # ------------------------------------------------
        print("\nCreating Audit Lines...")
        for entry in closing_entries:

            for l in entry.walkin_ids:
                self.env["cash.settlement.line"].create({
                    "cash_settlement_id": settlement.id,
                    "closing_entry_id": entry.id,
                    "pump_id": entry.pump_id.id,
                    "customer_id":default_customer,
                    "shift_id": entry.shift_id.id,
                    "shift_manager_id": entry.shift_manager_id.id,
                    "nozzle_id": entry.nozzle_id.id,
                    "fuel_id": entry.fuel_id.id,
                    "price": entry.price,
                    "quantity": l.quantity,
                    "amount": l.amount,
                    "sale_type": "walkin",
                    "dip_taken_qty":entry.dip_taken_qty,
                    "dip_returned_qty":entry.dip_returned_qty,
                })

            for l in entry.credit_ids:
                self.env["cash.settlement.line"].create({
                    "cash_settlement_id": settlement.id,
                    "closing_entry_id": entry.id,
                    "shift_id": entry.shift_id.id,
                    "shift_manager_id": entry.shift_manager_id.id,
                    "pump_id": entry.pump_id.id,
                    "nozzle_id": entry.nozzle_id.id,
                    "fuel_id": entry.fuel_id.id,
                    "price": entry.price,
                    "quantity": l.quantity,
                    "customer_id": l.customer_id.id,
                    "amount": l.amount,
                    "sale_type": "credit",
                })

            for l in entry.loyalty_line_ids:
                self.env["cash.settlement.line"].create({
                    "cash_settlement_id": settlement.id,
                    "closing_entry_id": entry.id,
                    "shift_id": entry.shift_id.id,
                    "shift_manager_id": entry.shift_manager_id.id,
                    "pump_id": entry.pump_id.id,
                    "nozzle_id": entry.nozzle_id.id,
                    "fuel_id": entry.fuel_id.id,
                    "price": entry.price,
                    "quantity": l.quantity,
                    "customer_id": l.customer_id.id,
                    "amount": l.amount,
                    "sale_type": "loyalty",
                })

        print("Audit Lines Created")

        # ------------------------------------------------
        # FINALIZE
        # ------------------------------------------------
        closing_entries.write({"state": "settled"})

        print("Settlement Submitted:", settlement.id)
        print("\n================ CASH SETTLEMENT END ==================\n")

        return settlement.id
