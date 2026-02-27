from odoo import api, fields, models
from datetime import datetime


class CustomerOutstandingReport(models.AbstractModel):
    _name = 'report.fuel_station.report_customer_outstanding_template'
    _description = 'Customer Outstanding Report'

    def _get_report_values(self, docids, data=None):
        data = data or {}
        form = data.get('form', {})

        start_date = datetime.strptime(form['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(form['end_date'], '%Y-%m-%d')
        partner_ids = form.get('partner_ids', [])

        # Partner domain
        partner_domain = [('is_credit_customer', '=', True)]
        if partner_ids:
            partner_domain.append(('id', 'in', partner_ids))

        partners = self.env['res.partner'].search(partner_domain)

        # Invoice domain
        invoice_domain = [
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('invoice_date', '>=', start_date.date()),
            ('invoice_date', '<=', end_date.date()),
            ('amount_residual', '>', 0),
        ]

        invoices = self.env['account.move'].search(invoice_domain)

        result = []

        for partner in partners:
            partner_data = {
                'id': partner.id,
                'name': partner.name,
                'count': 0,
                'total': 0.0,
                'outstanding': 0.0,
                'invoices': [],
            }

            for inv in invoices.filtered(lambda i: i.partner_id.id == partner.id):
                partner_data['count'] += 1
                partner_data['total'] += inv.amount_total
                partner_data['outstanding'] += inv.amount_residual

                partner_data['invoices'].append({
                    'name': inv.name,
                    'date': inv.invoice_date.strftime('%d-%m-%Y') if inv.invoice_date else '',
                    'due': inv.invoice_date_due.strftime('%d-%m-%Y') if inv.invoice_date_due else '',
                    'total': inv.amount_total,
                    'balance': inv.amount_residual,
                    'state': inv.state,
                    'payment_state': inv.payment_state,
                })

            if partner_data['count'] > 0:
                result.append(partner_data)

        return {
            'doc_ids': docids,
            'doc_model': 'res.partner',
            'start_date': start_date.strftime('%d-%m-%Y'),
            'end_date': end_date.strftime('%d-%m-%Y'),
            'data': result,
            'today': fields.Date.today().strftime('%d/%m/%Y'),
        }
