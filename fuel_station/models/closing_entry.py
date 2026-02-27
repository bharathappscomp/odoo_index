from odoo import api, fields, models, _


class ClosingEntry(models.Model):
    _name = 'closing.entry'
    _description = "Closing Entry"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, tracking=True)
    pump_id = fields.Many2one('fuel.station.pump', string="Pump", tracking=True)
    shift_id = fields.Many2one('fuel.station.shift', string="Shift", tracking=True)
    shift_manager_id = fields.Many2one('fuel.shift.manager', string="Shift Manager", tracking=True)
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle", tracking=True)
    fuel_id = fields.Many2one(
        'product.product',
        string="Fuel",
        related='nozzle_id.product_id',
        store=True,
        readonly=True, tracking=True
    )
    employee_id = fields.Many2one('hr.employee', string="Employee", tracking=True)
    price = fields.Monetary(string="Sold Price", tracking=True)
    start_reading = fields.Float(string="Start Reading", tracking=True)
    end_reading = fields.Float(string="End Reading", tracking=True)
    total_reading = fields.Float(
        string="Total Reading",
        compute="_compute_total_reading",
        store=True, tracking=True
    )
    total_sale_amount = fields.Monetary(string="Total Sales Amount To Get", compute="_compute_total_sale_amount", tracking=True)
    state = fields.Selection([('open', 'Open'), ('settled', 'Settled')], string='State', default='open', tracking=True)


    @api.depends('start_reading', 'end_reading')
    def _compute_total_reading(self):
        for record in self:
            if record.start_reading and record.end_reading:
                record.total_reading = record.end_reading - record.start_reading
            else:
                record.total_reading = 0.0

    opening_amount = fields.Monetary(string="Opening Amount In Hand", tracking=True)
    opening_journal_id = fields.Many2one(
        "account.journal",
        string="Opening Amount Journal",
        domain="[('type', 'in', ('cash', 'bank'))]", tracking=True
    )
    closing_amount = fields.Monetary(
        string="Closing Amount In Hand",
        compute="_compute_closing_amount",
        store=True, tracking=True
    )
    create_date = fields.Datetime(string="Closed On", tracking=True)

    credit_ids = fields.One2many('credit.sale.line', 'closing_entry_id', string='Credit Details', tracking=True)
    walkin_ids = fields.One2many('walkin.sale.line', 'closing_entry_id', string='Walk-in Details', tracking=True)

    payment_line_ids = fields.One2many(
        "closing.payment.line",
        "closing_entry_id",
        string="Payment Split", tracking=True
    )

    loyalty_line_ids = fields.One2many(
        "closing.loyalty.line",
        "closing_entry_id",
        string="Loyalty", tracking=True
    )

    dip_taken_qty = fields.Float(string="DIP Taken", tracking=True)
    dip_returned_qty = fields.Float(string="DIP Returned", tracking=True)

    @api.depends('payment_line_ids.amount')
    def _compute_closing_amount(self):
        for rec in self:
            rec.closing_amount = sum(rec.payment_line_ids.mapped('amount'))

    walkin_total_amount = fields.Monetary(
        string="Total Walk-in Amount",
        compute="_compute_walkin_total",
        store=True,
        tracking=True
    )

    credit_total_amount = fields.Monetary(
        string="Total Credit Amount",
        compute="_compute_credit_total",
        store=True,
        tracking=True
    )

    loyalty_total_amount = fields.Monetary(
        string="Total Loyalty Amount",
        compute="_compute_loyalty_total",
        store=True,
        tracking=True
    )

    @api.depends('loyalty_line_ids.amount')
    def _compute_loyalty_total(self):
        for rec in self:
            rec.loyalty_total_amount = sum(rec.loyalty_line_ids.mapped('amount'))

    @api.depends('credit_ids.amount')
    def _compute_credit_total(self):
        for rec in self:
            rec.credit_total_amount = sum(rec.credit_ids.mapped('amount'))

    @api.depends('walkin_ids.amount')
    def _compute_walkin_total(self):
        for rec in self:
            rec.walkin_total_amount = sum(rec.walkin_ids.mapped('amount'))

    @api.depends('walkin_ids.quantity','credit_ids.quantity','loyalty_line_ids.quantity')
    def _compute_total_sale_amount(self):
        for rec in self:
            walkin_total_qty = sum(rec.walkin_ids.mapped('quantity'))
            loyalty_total_qty = sum(rec.loyalty_line_ids.mapped('quantity'))
            total_qty = walkin_total_qty + loyalty_total_qty - (rec.dip_taken_qty or 0.0)
            rec.total_sale_amount = total_qty * rec.price


class WalkinSaleLine(models.Model):
    _name = 'walkin.sale.line'
    _description = 'Walkin Sale Line'

    closing_entry_id = fields.Many2one(
        'closing.entry',
        string='Closing Entry',
        required=True,
        ondelete='cascade'
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    shift_manager_id = fields.Many2one(
        'fuel.shift.manager',
        related='closing_entry_id.shift_manager_id',
        string="Shift",
        store=True, tracking=True
    )

    nozzle_id = fields.Many2one(
        'fuel.station.nozzle',
        related='closing_entry_id.nozzle_id',
        string="Nozzle",
        store=True
    )

    price = fields.Monetary(string="Sold Price")
    quantity = fields.Float(string="Qty", default=0.0, tracking=True)
    amount = fields.Monetary(
        string="Amount",
        compute="_compute_amount",
        store=True,
    )

    is_dip_adjustment = fields.Boolean(
        string="DIP Adjustment"
    )

    @api.depends(
        'quantity',
        'price',
    )
    def _compute_amount(self):
        for rec in self:
            price = 0.0

            if rec.quantity and rec.price:
                price = rec.quantity * rec.price

            rec.amount = price



class CreditSaleLine(models.Model):
    _name = 'credit.sale.line'
    _description = 'Credit Sale Line'

    closing_entry_id = fields.Many2one(
        'closing.entry',
        string='Closing Entry',
        required=True,
        ondelete='cascade'
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now
    )

    customer_id = fields.Many2one(
        'res.partner',
        string="Credit Customer",
        required=True
    )

    shift_manager_id = fields.Many2one(
        'fuel.shift.manager',
        related='closing_entry_id.shift_manager_id',
        string="Shift",
        store=True
    )

    nozzle_id = fields.Many2one(
        'fuel.station.nozzle',
        related='closing_entry_id.nozzle_id',
        string="Nozzle",
        store=True
    )

    vehicle_no = fields.Char(string="Vehicle No")
    price = fields.Monetary(string="Sold Price")
    quantity = fields.Float(string="Qty", default=0.0)
    amount = fields.Monetary(
        string="Amount",
        compute="_compute_amount",
        store=True,
    )



    @api.depends(
        'quantity',
        'price',
    )
    def _compute_amount(self):
        for rec in self:
            price = 0.0

            if rec.quantity and rec.price:
                price = rec.quantity * rec.price

            rec.amount = price


class ClosingLoyaltyLine(models.Model):
    _name = "closing.loyalty.line"

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    closing_entry_id = fields.Many2one(
        "closing.entry",
        string="Closing Entry",
        required=True,
        ondelete="cascade"
    )

    shift_manager_id = fields.Many2one(
        'fuel.shift.manager',
        related='closing_entry_id.shift_manager_id',
        string="Shift",
        store=True
    )

    nozzle_id = fields.Many2one(
        'fuel.station.nozzle',
        related='closing_entry_id.nozzle_id',
        string="Nozzle",
        store=True
    )

    customer_id = fields.Many2one(
        'res.partner',
        string="Loyalty Customer",
        required=True
    )

    price = fields.Monetary(string="Sold Price ")
    quantity = fields.Float(string="Qty", default=0.0)

    amount = fields.Monetary(
        string="Amount",
        compute="_compute_amount",
        store=True,
    )

    @api.depends(
        'quantity',
        'price',
    )
    def _compute_amount(self):
        for rec in self:
            price = 0.0

            if rec.quantity and rec.price:
                price = rec.quantity * rec.price

            rec.amount = price


class ClosingPaymentLine(models.Model):
    _name = "closing.payment.line"
    _description = "Shift Closing Payment Split"
    _order = "id"

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True
    )

    closing_entry_id = fields.Many2one(
        "closing.entry",
        string="Closing Entry",
        required=True,
        ondelete="cascade"
    )

    journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        required=True,
        domain="[('type', 'in', ('cash', 'bank'))]"
    )

    amount = fields.Monetary(
        string="Amount",
        required=True
    )

    shift_manager_id = fields.Many2one(
        'fuel.shift.manager',
        related='closing_entry_id.shift_manager_id',
        string="Shift",
        store=True
    )

    nozzle_id = fields.Many2one(
        'fuel.station.nozzle',
        related='closing_entry_id.nozzle_id',
        string="Nozzle",
        store=True
    )