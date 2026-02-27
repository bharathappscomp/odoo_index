from odoo import api, fields, models
from datetime import datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_customer_outstanding_data(self, start_date, end_date, partner_ids=None):
        partner_ids = partner_ids or []

        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        partner_domain = [('is_credit_customer', '=', True)]
        if partner_ids:
            partner_domain.append(('id', 'in', partner_ids))

        partners = self.search(partner_domain)

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
            pdata = {
                'id': partner.id,
                'name': partner.name,
                'count': 0,
                'total': 0.0,
                'outstanding': 0.0,
                'invoices': [],
            }

            for inv in invoices.filtered(lambda i: i.partner_id.id == partner.id):
                pdata['count'] += 1
                pdata['total'] += inv.amount_total
                pdata['outstanding'] += inv.amount_residual

                pdata['invoices'].append({
                    'name': inv.name,
                    'date': inv.invoice_date.strftime('%d-%m-%Y') if inv.invoice_date else '',
                    'due': inv.invoice_date_due.strftime('%d-%m-%Y') if inv.invoice_date_due else '',
                    'total': inv.amount_total,
                    'balance': inv.amount_residual,
                    'state': inv.state,
                    'payment_state': inv.payment_state,
                })

            if pdata['count']:
                result.append(pdata)

        return result
