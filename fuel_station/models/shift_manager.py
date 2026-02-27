from odoo import api, fields, models, _


class FuelShiftManager(models.Model):
    _name = 'fuel.shift.manager'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Fuel Shift Manager"

    shift_id = fields.Many2one('fuel.station.shift', string="Shift", tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", tracking=True)
    employee_coa_id = fields.Many2one(
        'account.account',
        related='employee_id.coa_id',
        string='Employee Petty Cash Account',
        store=True,
        readonly=True, tracking=True
    )

    assigned_date = fields.Date(string="Assigned On", tracking=True)
    pump_id = fields.Many2one('fuel.station.pump', string="Pump", tracking=True)
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle", tracking=True)
    fuel_id = fields.Many2one(
        'product.product',
        string="Fuel",
        related='nozzle_id.product_id',
        store=True,
        readonly=True, tracking=True
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, tracking=True)
    start_reading = fields.Float(string="Start Reading", tracking=True)
    end_reading = fields.Float(string="End Reading", tracking=True)
    opening_amount = fields.Monetary(string="Opening Amount In Hand", tracking=True)
    opening_journal_id = fields.Many2one(
        "account.journal",
        string="Opening Amount Journal",
        domain="[('type', 'in', ('cash', 'bank'))]", tracking=True
    )
    state = fields.Selection([('open', 'Open'), ('close', 'Closed')], string='State', default='open', tracking=True)

    closing_amount = fields.Monetary(
        string="Closing Amount In Hand",
        compute="_compute_closing_amount",
        store=False, tracking=True
    )

    price = fields.Monetary(string="Sold Price", tracking=True)

    dip_test = fields.Boolean(string="DIP Test", tracking=True)
    dip_taken_qty = fields.Float(string="DIP Taken", tracking=True)
    dip_returned_qty = fields.Float(string="DIP Returned", tracking=True)

    # 🔁 Reassignment flags
    reassigned_before_closing = fields.Boolean(
        string="Reassigned Before Closing",
        default=False,
        tracking=True,
    )

    reassigned_after_closing = fields.Boolean(
        string="Reassigned After Closing",
        default=False,
        tracking=True,
    )

    def _compute_closing_amount(self):
        for rec in self:

            closing = self.env['closing.entry'].search(
                [('shift_manager_id', '=', rec.id)],
                limit=1,
                order='id desc'
            )
            rec.closing_amount = closing.closing_amount if closing else 0.0
