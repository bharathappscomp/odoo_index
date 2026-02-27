from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_credit_customer = fields.Boolean(string="Credit Customer", default=False)
    is_loyalty_customer = fields.Boolean(string="Loyalty Customer", default=False)
    is_default_customer = fields.Boolean(string="Default Customer", default=False)

    vehicle_line_ids = fields.One2many(
        'credit.vehicle.line',
        'credit_customer_id',
        string='Customer Vehicles'
    )


class CreditVehicleLine(models.Model):
    _name = 'credit.vehicle.line'
    _description = 'Credit Customer Vehicle'

    credit_customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        ondelete='cascade',
        required=True
    )

    vehicle = fields.Char(
        string='Vehicle Number',
        required=True
    )
