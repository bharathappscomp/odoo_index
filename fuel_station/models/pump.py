from odoo import api, fields, models, _

class FuelStationPump(models.Model):
    _name = 'fuel.station.pump'
    _description = "Fuel Station Pump"

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    line_ids = fields.One2many('fuel.station.line', 'pump_id', string="Lines")
