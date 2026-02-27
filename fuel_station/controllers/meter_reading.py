from odoo import api, models
from odoo import http
from odoo.http import request
from datetime import datetime, time
from collections import defaultdict



class ClosingEntry(models.Model):
    _inherit = 'closing.entry'

    @api.model
    def get_meter_readings_by_date(self, date):

        domain = [
            ('create_date', '>=', f'{date} 00:00:00'),
            ('create_date', '<=', f'{date} 23:59:59'),
        ]

        records = self.search(domain, order="pump_id, nozzle_id, start_reading")

        grouped = {}

        for rec in records:
            key = (rec.pump_id.id, rec.nozzle_id.id)

            start = rec.start_reading or 0.0
            end = rec.end_reading or 0.0
            ltrs = end - start
            rate = rec.price or 0.0
            amount = ltrs * rate

            if key not in grouped:
                grouped[key] = {
                    'pump': rec.pump_id.name,
                    'nozzle': rec.nozzle_id.name,
                    'fuel': rec.fuel_id.name if rec.fuel_id else '',
                    'opening': start,
                    'closing': end,
                    'ltrs': 0.0,
                    'rate': rate,
                    'amount': 0.0,
                }
            else:
                grouped[key]['opening'] = min(grouped[key]['opening'], start)
                grouped[key]['closing'] = max(grouped[key]['closing'], end)

            grouped[key]['ltrs'] += ltrs
            grouped[key]['amount'] += amount

            if rate:
                grouped[key]['rate'] = rate

        # ---------------------------
        # METER LINES (UNCHANGED)
        # ---------------------------
        meter_lines = list(grouped.values())

        # ---------------------------
        # TOTAL SALES (NEW)
        # ---------------------------
        product_map = {}

        for line in meter_lines:
            product = line['fuel']

            if product not in product_map:
                product_map[product] = {
                    'product': product,
                    'ltrs': 0.0,
                    'rate': line['rate'],
                    'amount': 0.0,
                }

            product_map[product]['ltrs'] += line['ltrs']
            product_map[product]['amount'] += line['amount']

        total_sales = list(product_map.values())

        # ---------------------------
        # CREDIT SALES (NEW)
        # ---------------------------
        credit_lines = self.env['credit.sale.line'].search([
            ('closing_entry_id.create_date', '>=', f'{date} 00:00:00'),
            ('closing_entry_id.create_date', '<=', f'{date} 23:59:59'),
        ])

        credit_map = {}

        for line in credit_lines:
            product = line.nozzle_id.product_id.name if line.nozzle_id and line.nozzle_id.product_id else ''
            qty = line.quantity or 0.0
            rate = line.price or 0.0
            amount = line.amount or 0.0

            if product not in credit_map:
                credit_map[product] = {
                    'product': product,
                    'qty': 0.0,
                    'rate': rate,
                    'amount': 0.0,
                }

            credit_map[product]['qty'] += qty
            credit_map[product]['amount'] += amount

            if rate:
                credit_map[product]['rate'] = rate

        credit_sales = list(credit_map.values())

        # ✅ RETURN BOTH
        return {
            'meter_lines': meter_lines,
            'total_sales': total_sales,
            'credit_sales': credit_sales,
        }

    @api.model
    def get_shift_wise_data(self, start_date, end_date):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        start_dt = datetime.combine(start_date.date(), time.min)
        end_dt = datetime.combine(end_date.date(), time.max)

        domain = [
            ('create_date', '>=', start_dt),
            ('create_date', '<=', end_dt),
        ]

        closings = self.search(domain, order="shift_id, pump_id")

        shift_data = defaultdict(list)

        for rec in closings:
            shift_data[rec.shift_id.name].append({
                'date': rec.create_date.strftime('%d-%m-%Y'),
                'pump': rec.pump_id.name,
                'nozzle': rec.nozzle_id.name,
                'fuel': rec.fuel_id.name,
                'start_reading': rec.start_reading,
                'end_reading': rec.end_reading,
                'total_reading': rec.total_reading,
                'price': rec.price,
                'amount': rec.total_reading * rec.price,
            })

        return dict(shift_data)


