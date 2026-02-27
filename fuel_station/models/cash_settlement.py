from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CashSettlement(models.Model):
    _name = "cash.settlement"
    _description = "Cash Settlement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
        tracking=True,
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        readonly=True,
        tracking=True,
    )

    shift_id = fields.Many2one(
        "fuel.station.shift",
        string="Shift",
        required=True,
        readonly=True,
        tracking=True,
    )

    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        tracking=True,
    )

    expected_amount = fields.Monetary(
        string="Expected Amount",
        readonly=True,
        tracking=True,
    )

    submitted_amount = fields.Monetary(
        string="Submitted Amount",
        compute="_compute_submitted_amount",
        store=True,
        tracking=True,
    )

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
        ],
        default="draft",
        tracking=True,
    )

    closing_entry_ids = fields.Many2many(
        "closing.entry",
        string="Closing Entries",
        readonly=True,
    )

    line_ids = fields.One2many(
        "cash.settlement.line",
        "cash_settlement_id",
        string="Settlement Lines",
        readonly=True,
    )

    payment_line_ids = fields.One2many(
        "cash.settlement.payment.line",
        "cash_settlement_id",
        string="Payment Lines",
    )

    move_ids = fields.One2many(
        "cash.settlement.move",
        "cash_settlement_id",
        string="Journal Entries",
        readonly=True,
    )

    sale_order_count = fields.Integer(
        compute="_compute_counts",
        string="Sale Orders"
    )
    invoice_count = fields.Integer(
        compute="_compute_counts",
        string="Invoices"
    )
    payment_count = fields.Integer(
        compute="_compute_counts",
        string="Payments"
    )

    @api.depends("shift_id", "date")
    def _compute_name(self):
        for rec in self:
            if rec.shift_id and rec.date:
                rec.name = f"{rec.shift_id.name} - {rec.date}"
            else:
                rec.name = "Cash Settlement"

    def _compute_counts(self):
        SaleOrder = self.env['sale.order']
        AccountMove = self.env['account.move']
        AccountPayment = self.env['account.payment']

        for rec in self:
            rec.sale_order_count = SaleOrder.search_count([
                ('settlement_id', '=', rec.id)
            ])

            rec.invoice_count = AccountMove.search_count([
                ('settlement_id', '=', rec.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ])

            rec.payment_count = AccountPayment.search_count([
                ('settlement_id', '=', rec.id),
            ])

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Orders'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('settlement_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [
                ('settlement_id', '=', self.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
            ],
            'context': {'create': False},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('settlement_id', '=', self.id)],
            'context': {'create': False},
        }

    @api.depends("payment_line_ids.amount")
    def _compute_submitted_amount(self):
        for rec in self:
            rec.submitted_amount = sum(rec.payment_line_ids.mapped("amount"))

    def create_sale_order(self):
        """
        Create Sale Orders from Cash Settlement Lines
        Uses customer_id as partner
        Passes dip_taken_qty and dip_returned_qty to Sale Order
        """

        SaleOrder = self.env["sale.order"]

        for settlement in self:

            settlement._create_and_post_payments()

            if not settlement.line_ids:
                raise ValidationError(_("No settlement lines to create sale orders."))

            # ------------------------------------------------
            # GROUP SETTLEMENT LINES
            # ------------------------------------------------
            grouped = {}

            for line in settlement.line_ids:

                if not line.customer_id:
                    raise ValidationError(
                        _("Customer missing on settlement line %s") % line.id
                    )

                key = (
                    line.sale_type,
                    line.customer_id.id,
                    line.fuel_id.id,
                    line.nozzle_id.id,
                    line.shift_manager_id.id,
                )

                grouped.setdefault(key, {
                    "quantity": 0.0,
                    "dip_taken": 0.0,
                    "dip_returned": 0.0,
                    "price": line.price,
                })

                grouped[key]["quantity"] += line.quantity
                grouped[key]["dip_taken"] += line.dip_taken_qty or 0.0
                grouped[key]["dip_returned"] += line.dip_returned_qty or 0.0

            # ------------------------------------------------
            # CREATE SALE ORDERS
            # ------------------------------------------------
            for (
                    sale_type,
                    partner_id,
                    product_id,
                    nozzle_id,
                    shift_manager_id,
            ), data in grouped.items():

                qty = data["quantity"]
                if qty <= 0:
                    continue

                if sale_type == "walkin":
                    fuel_sale_type = "walk"
                elif sale_type == "credit":
                    fuel_sale_type = "credit"
                else:
                    fuel_sale_type = "loyalty"

                order_vals = {
                    "partner_id": partner_id,
                    "user_id": self.env.uid,
                    "is_fuel_sale": True,
                    "fuel_sale_type": fuel_sale_type,
                    "settlement_id": settlement.id,
                    "shift_manager_id": shift_manager_id,
                    "nozzle_id": nozzle_id,
                    "dip_taken_qty": data["dip_taken"],
                    "dip_returned_qty": data["dip_returned"],
                    "order_line": [(0, 0, {
                        "product_id": product_id,
                        "product_uom_qty": qty,
                        "price_unit": data["price"],
                    })],
                }

                auto_confirm = self.env['ir.config_parameter'].sudo().get_param(
                    'fuel_station.auto_confirm_sale'
                ) in ('True', 'true', True)

                order = SaleOrder.with_context(from_fuel_station=True).create(order_vals)

                if auto_confirm:
                    order.action_confirm()
        self.state = "submitted"

    def _create_and_post_payments(self):
        AccountPayment = self.env["account.payment"]

        default_customer = self.env['res.partner'].search([('is_default_customer', '=', True)])

        for settlement in self:
            for line in settlement.payment_line_ids:
                if line.payment_id:
                    continue

                payment_vals = {
                    "partner_id": default_customer,
                    "payment_type": "inbound",
                    # "partner_type": "customer",
                    "amount": line.amount,
                    "journal_id": line.journal_id.id,
                    "date": settlement.date,
                    "ref": line.ref or f"Cash Settlement {settlement.id}",
                    # "company_id": settlement.company_id.id,
                    "is_fuel_payment": True,
                    "is_petty_cash": line.payment_type == "petty_cash",
                    "settlement_id": settlement.id,
                }

                payment = AccountPayment.create(payment_vals)

                payment.action_post()

                line.payment_id = payment.id
                line.state = "posted"


class CashSettlementLine(models.Model):
    _name = "cash.settlement.line"
    _description = "Cash Settlement Line"

    cash_settlement_id = fields.Many2one(
        "cash.settlement",
        required=True,
        ondelete="cascade",
    )

    closing_entry_id = fields.Many2one(
        "closing.entry",
        required=True,
        readonly=True,
    )

    customer_id = fields.Many2one(
        'res.partner',
        string="Customer",
        required=True
    )

    shift_id = fields.Many2one('fuel.station.shift', string="Shift", tracking=True)
    shift_manager_id = fields.Many2one('fuel.shift.manager', string="Shift Manager", tracking=True)

    pump_id = fields.Many2one(
        "fuel.station.pump",
        readonly=True,
    )

    nozzle_id = fields.Many2one(
        "fuel.station.nozzle",
        readonly=True,
    )

    fuel_id = fields.Many2one(
        "product.product",
        readonly=True,
    )

    price = fields.Monetary(
        string="Sold Price",
        readonly=True,
    )

    quantity = fields.Float(
        readonly=True,
    )

    amount = fields.Monetary(
        readonly=True,
    )

    sale_type = fields.Selection(
        [
            ("walkin", "Walk-in"),
            ("credit", "Credit"),
            ("loyalty", "Loyalty"),
        ],
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="cash_settlement_id.currency_id",
        readonly=True,
    )

    dip_taken_qty = fields.Float(string="DIP Taken", tracking=True)
    dip_returned_qty = fields.Float(string="DIP Returned", tracking=True)


class CashSettlementPaymentLine(models.Model):
    _name = "cash.settlement.payment.line"
    _description = "Cash Settlement Payment Line"

    cash_settlement_id = fields.Many2one(
        "cash.settlement",
        required=True,
        ondelete="cascade",
    )

    payment_id = fields.Many2one(
        "account.payment",
        string="Payment",
        readonly=True,
        ondelete="set null",
    )

    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[('type', 'in', ('cash', 'bank'))]",
    )

    amount = fields.Monetary(required=True)

    payment_type = fields.Selection(
        [
            ("shift", "Shift Sale"),
            ("petty_cash", "Petty Cash"),
            ("shortage", "Shortage"),
        ],
        required=True,
    )

    ref = fields.Char()

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("posted", "Posted"),
        ],
        default="draft",
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="cash_settlement_id.currency_id",
        readonly=True,
    )


class CashSettlementMove(models.Model):
    _name = "cash.settlement.move"
    _description = "Cash Settlement Journal Entry"

    cash_settlement_id = fields.Many2one(
        "cash.settlement",
        required=True,
        ondelete="cascade",
    )

    move_id = fields.Many2one(
        "account.move",
        required=True,
        readonly=True,
    )

    move_type = fields.Selection(
        [
            ("petty_return", "Petty Cash Return"),
            ("shortage", "Shortage"),
        ],
        required=True,
        readonly=True,
    )
