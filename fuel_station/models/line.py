from odoo import api, fields, models, _

class FuelStationLine(models.Model):
    _name = 'fuel.station.line'
    _description = "Fuel Station Line"

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    pump_id = fields.Many2one('fuel.station.pump', string="Pump")
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    start_reading = fields.Float(string="Start Reading")
    end_reading = fields.Float(string="End Reading")
    opening_amount = fields.Monetary(string="Opening Amount In Hand")
    closing_amount = fields.Monetary(string="Closing Amount In Hand")
    create_date = fields.Datetime(string="Created On")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
