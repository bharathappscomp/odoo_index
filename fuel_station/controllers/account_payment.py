from odoo import api, fields, models
from datetime import datetime


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.model
    def get_payment_mode_data(self, start_date, end_date, journal_ids=None):
        journal_ids = journal_ids or []

        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        domain = [
            ('date', '>=', start_date.date()),
            ('date', '<=', end_date.date()),
            ('state', '=', 'posted'),
            ('is_fuel_payment', '=', True),
        ]

        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))

        payments = self.search(domain)

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

            journal_summary[journal_name] = journal_summary.get(journal_name, 0.0) + amount
            pump_summary[pump_name] = pump_summary.get(pump_name, 0.0) + amount
            nozzle_summary[nozzle_name] = nozzle_summary.get(nozzle_name, 0.0) + amount

            rows.append({
                'row_key': pay.id,
                'date': pay.date.strftime('%d-%m-%Y') if pay.date else '',
                'journal': journal_name,
                'pump': pump_name,
                'nozzle': nozzle_name,
                'amount': amount,
            })

        return {
            'rows': rows,
            'journal_summary': journal_summary,
            'pump_summary': pump_summary,
            'nozzle_summary': nozzle_summary,
            'total': total_amount,
        }
