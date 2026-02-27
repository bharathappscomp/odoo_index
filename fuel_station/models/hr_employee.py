from odoo import api, fields, models, _

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    password = fields.Char("Password")
    petty_cash_need = fields.Boolean(
        string='Petty Cash Allocation',
        help='Check this box if the employee needs petty cash for their work.',
        default=False,
    )
    coa_id = fields.Many2one('account.account', string='Petty Cash Account', store=True)

    petty_cash_balance = fields.Float(
        string='Petty Cash Balance',
        compute='_compute_petty_cash_balance',
        store=False,
        help='Current balance of the petty cash for the employee.',
    )

    @api.depends('coa_id')
    def _compute_petty_cash_balance(self):
        MoveLine = self.env['account.move.line']
        for employee in self:
            if not employee.coa_id:
                employee.petty_cash_balance = 0.0
                continue

            lines = MoveLine.search([
                ('account_id', '=', employee.coa_id.id),
                ('move_id.state', '=', 'posted'),
            ])

            balance = sum(lines.mapped('debit')) - sum(lines.mapped('credit'))
            employee.petty_cash_balance = balance

    def create_petty_cash_account(self):
        for employee in self:
            if employee.coa_id:
                continue

            cash_account = self.env['account.account'].search([
                ('account_type', '=', 'asset_cash'),
                ('company_id', '=', employee.company_id.id),
            ], limit=1)

            if not cash_account:
                raise UserError(_("No Cash account found for this company."))

            petty_account = cash_account.copy()

            petty_account.write({
                'name': f'{employee.name} - Petty Cash',
            })

            employee.coa_id = petty_account.id

    def create_petty_cash_record(self, amount, shift_id, date, employee_name):
        self.ensure_one()

        if amount <= 0:
            raise UserError(_("Amount must be greater than zero."))

        if not self.coa_id:
            raise UserError(_("Employee does not have a Petty Cash account."))

        shift = self.env['fuel.station.shift'].browse(shift_id)
        shift_name = shift.name if shift else "Unknown Shift"

        company = self.company_id

        # Find cash journal
        cash_journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', company.id),
        ], limit=1)

        if not cash_journal:
            raise UserError(_("No Cash journal found for this company."))

        narration = f"Petty Cash | {employee_name} | {shift_name} | {date}"

        move = self.env['account.move'].create({
            'journal_id': cash_journal.id,
            'date': date,
            'ref': narration,
            'line_ids': [
                # Credit Cash
                (0, 0, {
                    'account_id': cash_journal.default_account_id.id,
                    'credit': amount,
                    'debit': 0.0,
                    'name': narration,
                }),
                # Debit Employee Petty Cash Account
                (0, 0, {
                    'account_id': self.coa_id.id,
                    'debit': amount,
                    'credit': 0.0,
                    'name': narration,
                }),
            ],
        })

        move.action_post()
        # self._compute_petty_cash_balance()

        return {
            'status': 'success',
            'move_id': move.id,
        }