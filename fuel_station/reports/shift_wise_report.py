from odoo import api, fields, models
from collections import defaultdict
from datetime import datetime, time


class ShiftWiseMeterReport(models.AbstractModel):
    _name = 'report.fuel_station.report_shift_wise_template'
    _description = 'Shift Wise Meter Reading Report'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        form = data.get('form', {})

        start_date = datetime.strptime(form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(form['end_date'], '%Y-%m-%d')

        start_dt = datetime.combine(start_date.date(), time.min)
        end_dt = datetime.combine(end_date.date(), time.max)

        domain = [
            ('create_date', '>=', start_dt),
            ('create_date', '<=', end_dt),
        ]

        closings = self.env['closing.entry'].search(domain, order="shift_id, pump_id")

        shift_data = defaultdict(list)

        for rec in closings:
            shift_data[rec.shift_id.name].append({
                'date': fields.Datetime.to_datetime(rec.create_date).strftime('%d-%m-%Y'),
                'pump': rec.pump_id.name,
                'nozzle': rec.nozzle_id.name,
                'fuel': rec.fuel_id.name,
                'start_reading': rec.start_reading,
                'end_reading': rec.end_reading,
                'total_reading': rec.total_reading,
                'price': rec.price,
                'amount': rec.total_reading * rec.price,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'closing.entry',
            'start_date': start_date.strftime('%d-%m-%Y'),
            'end_date': end_date.strftime('%d-%m-%Y'),
            'shift_data': dict(shift_data),
            'today': fields.Date.today().strftime('%d/%m/%Y'),
        }
