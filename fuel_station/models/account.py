from odoo import api, fields, models, _

class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_fuel_payment = fields.Boolean(string="Fuel Payment")
    is_petty_cash = fields.Boolean(string="Petty Cash Payment")
    shift_manager_id = fields.Many2one('fuel.shift.manager', string="Shift Manager")
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle")
    settlement_id = fields.Many2one(
        "cash.settlement",
        string="Cash Settlement",
        readonly=True,
        copy=False,
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    is_fuel_invoice = fields.Boolean(string="Fuel Invoice")
    fuel_inv_type = fields.Selection([('walk', 'Walk-In'), ('credit', 'Credit Sale'), ('loyalty', 'Loyalty')],
                                      string='Fuel Invoice Type')
    shift_manager_id = fields.Many2one('fuel.shift.manager', string="Shift Manager")
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle")
    settlement_id = fields.Many2one(
        "cash.settlement",
        string="Cash Settlement",
        readonly=True,
        copy=False,
    )
