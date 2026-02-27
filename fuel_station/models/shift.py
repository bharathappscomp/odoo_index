from odoo import api, fields, models, _

class FuelStationShift(models.Model):
    _name = 'fuel.station.shift'
    _description = "Fuel Station Shift"

    name = fields.Char(string="Name")
    sequence = fields.Integer(string="Sequence")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    start_time = fields.Float(string="Start Time")
    end_time = fields.Float(string="End Time")
    duration = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration",
        store=True
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration = rec.end_time - rec.start_time
            else:
                rec.duration = 0.0
