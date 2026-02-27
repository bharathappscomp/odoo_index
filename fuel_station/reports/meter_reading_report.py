from odoo import api, models

class MeterReadingReport(models.AbstractModel):
    _name = 'report.fuel_station.meter_reading_report_template'
    _description = 'Meter Reading PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        date = data.get('date')

        # -----------------------------
        # SEARCH CLOSING ENTRIES
        # -----------------------------
        domain = [
            ('create_date', '>=', f'{date} 00:00:00'),
            ('create_date', '<=', f'{date} 23:59:59'),
        ]

        print("domain:", domain)
        records = self.env['closing.entry'].search(
            domain, order="pump_id, nozzle_id, start_reading"
        )

        print("records:", records)

        # -----------------------------
        # METER LINES
        # -----------------------------
        meter_lines = []
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

        meter_lines = list(grouped.values())

        # -----------------------------
        # TOTAL SALES
        # -----------------------------
        total_sales = []
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

        # -----------------------------
        # CREDIT SALES
        # -----------------------------
        credit_sales = []
        credit_map = {}

        credit_lines = self.env['credit.sale.line'].search([
            ('closing_entry_id.create_date', '>=', f'{date} 00:00:00'),
            ('closing_entry_id.create_date', '<=', f'{date} 23:59:59'),
        ])

        for line in credit_lines:
            product = line.nozzle_id.product_id.name if line.nozzle_id else ''
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

        credit_sales = list(credit_map.values())

        # -----------------------------
        # RETURN (LIKE MEDICAL REPORT)
        # -----------------------------
        return {
            'date': date,
            'meter_lines': meter_lines,
            'total_sales': total_sales,
            'credit_sales': credit_sales,
        }
