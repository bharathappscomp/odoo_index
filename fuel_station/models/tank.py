from odoo import api, fields, models, _

class FuelStationTank(models.Model):
    _name = 'fuel.station.tank'
    _description = "Fuel Station Tank"

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    location_id = fields.Many2one(
        'stock.location',
        string="Tank Location",
        required=True,
        ondelete='restrict'
    )
    product_id = fields.Many2one('product.product', string="Fuel")
    capacity_liters = fields.Float(
        string="Tank Capacity (Liters)",
        required=True
    )
