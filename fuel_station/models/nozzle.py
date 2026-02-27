from odoo import api, fields, models, _

class FuelStationNozzle(models.Model):
    _name = 'fuel.station.nozzle'
    _description = "Fuel Station Nozzle"

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    pump_id = fields.Many2one('fuel.station.pump', string="Pump")
    product_id = fields.Many2one('product.product', string="Fuel")
    tank_id = fields.Many2one('fuel.station.tank', string="Tank")
    start_reading = fields.Float(string="Start Reading")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    shift_id = fields.Many2one('fuel.station.shift', string="Shift")
    end_reading = fields.Float(string="End Reading")
    line_ids = fields.One2many('fuel.station.line', 'nozzle_id', string="Lines")
