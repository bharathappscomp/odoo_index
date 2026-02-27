from odoo import api, fields, models
from datetime import datetime


class PaymentModePDFReport(models.AbstractModel):
    _name = 'report.fuel_station.report_payment_mode_template'
    _description = 'Payment Mode Report'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        form = data.get('form', {})

        start_date = datetime.strptime(form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(form['end_date'], '%Y-%m-%d')
        journal_ids = form.get('journal_ids', [])

        domain = [
            ('date', '>=', start_date.date()),
            ('date', '<=', end_date.date()),
            ('state', '=', 'posted'),
            ('is_fuel_payment', '=', True),
        ]

        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        payments = self.env['account.payment'].search(domain)

        rows = []
        journal_summary = {}
        pump_summary = {}
        nozzle_summary = {}
        total_amount = 0.0

        for pay in payments:
            amount = round(pay.amount, 2)
            total_amount += amount

            journal_name = pay.journal_id.name
            pump_name = pay.shift_manager_id.pump_id.name if pay.shift_manager_id else 'N/A'
            nozzle_name = pay.nozzle_id.name if pay.nozzle_id else 'N/A'

            # ---- Journal Summary ----
            journal_summary[journal_name] = journal_summary.get(journal_name, 0.0) + amount

            # ---- Pump Summary ----
            pump_summary[pump_name] = pump_summary.get(pump_name, 0.0) + amount

            # ---- Nozzle Summary ----
            nozzle_summary[nozzle_name] = nozzle_summary.get(nozzle_name, 0.0) + amount

            # ---- Detail Rows ----
            rows.append({
                'date': pay.date.strftime('%d-%m-%Y') if pay.date else '',
                'journal': journal_name,
                'pump': pump_name,
                'nozzle': nozzle_name,
                'amount': amount,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'account.payment',
            'start_date': start_date.strftime('%d-%m-%Y'),
            'end_date': end_date.strftime('%d-%m-%Y'),
            'data': rows,

            # ✅ SUMMARY TABLES
            'journal_summary': journal_summary,
            'pump_summary': pump_summary,
            'nozzle_summary': nozzle_summary,

            'total': total_amount,
            'currency': self.env.company.currency_id,
            'today': fields.Date.today().strftime('%d/%m/%Y'),
        }
