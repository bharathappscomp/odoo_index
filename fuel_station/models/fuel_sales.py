from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_fuel_sale = fields.Boolean(string="Fuel Sale")
    fuel_sale_type = fields.Selection([('walk', 'Walk-In'), ('credit', 'Credit Sale'), ('loyalty', 'Loyalty')],
                                      string='Fuel Sale Type')
    shift_manager_id = fields.Many2one('fuel.shift.manager', string="Shift Manager")
    nozzle_id = fields.Many2one('fuel.station.nozzle', string="Nozzle")

    dip_taken_qty = fields.Float(string="DIP Taken", tracking=True)
    dip_returned_qty = fields.Float(string="DIP Returned", tracking=True)

    settlement_id = fields.Many2one(
        "cash.settlement",
        string="Cash Settlement",
        readonly=True,
        index=True,
    )

    @api.model
    def create(self, vals):
        if self.env.context.get("from_fuel_station"):
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sale.order.fuel"
                ) or "/"
        return super().create(vals)

    def action_confirm(self):
        res = super().action_confirm()
        print("SaleOrder action_confirm")

        auto_confirm = self.env['ir.config_parameter'].sudo().get_param(
            'fuel_station.auto_confirm_sale'
        )
        auto_confirm = auto_confirm in ('True', 'true', True)

        if not auto_confirm:
            return res

        for sale in self:
            if not sale.is_fuel_sale or not sale.nozzle_id:
                continue

            shift = sale.shift_manager_id
            if not shift:
                continue

            tank = sale.nozzle_id.tank_id
            if not tank or not tank.location_id:
                raise ValidationError(
                    "No tank location configured for the selected nozzle."
                )

            tank_location = tank.location_id

            scrap_location = self.env['stock.location'].search(
                [('scrap_location', '=', True)], limit=1
            )
            if not scrap_location:
                raise ValidationError("No scrap location configured in Inventory.")

            # ------------------------------------------------
            # DELIVERY & DIP LOGIC (UNCHANGED)
            # ------------------------------------------------
            for picking in sale.picking_ids:
                if picking.state in ('done', 'cancel'):
                    continue

                picking.location_id = tank_location.id

                for move in picking.move_ids_without_package:
                    if (
                            move.product_id.is_fuel_product
                            and move.product_id != tank.product_id
                    ):
                        raise ValidationError("Product does not match the tank fuel.")

                    move.location_id = tank_location.id
                    move.quantity = move.product_uom_qty

                picking.button_validate()

                # ⭐ DIP RETURN
                if (
                        sale.fuel_sale_type == 'walk'
                        and shift.dip_taken_qty
                        and not float_is_zero(
                    shift.dip_taken_qty,
                    precision_rounding=tank.product_id.uom_id.rounding
                )
                ):
                    wizard = self.env['stock.return.picking'].with_context(
                        active_id=picking.id,
                        active_ids=[picking.id],
                        active_model='stock.picking',
                    ).create({})

                    for line in wizard.product_return_moves:
                        line.quantity = (
                            shift.dip_taken_qty
                            if line.product_id == tank.product_id
                            else 0
                        )

                    result = wizard.create_returns()
                    return_picking = self.env['stock.picking'].browse(result['res_id'])
                    if return_picking.state != 'done':
                        return_picking.button_validate()

                # 🔥 DIP SCRAP
                scrap_qty = shift.dip_taken_qty - shift.dip_returned_qty
                if (
                        sale.fuel_sale_type == 'walk'
                        and scrap_qty > 0
                        and not float_is_zero(
                    scrap_qty,
                    precision_rounding=tank.product_id.uom_id.rounding
                )
                ):
                    scrap = self.env['stock.scrap'].create({
                        'product_id': tank.product_id.id,
                        'scrap_qty': scrap_qty,
                        'product_uom_id': tank.product_id.uom_id.id,
                        'location_id': tank_location.id,
                        'scrap_location_id': scrap_location.id,
                        'origin': f"{sale.name} - DIP Scrap",
                    })
                    if scrap.state != 'done':
                        scrap.action_validate()

            invoices = sale._create_invoices()
            invoices.action_post()

            # 🔥 NEW RECONCILIATION LOGIC (SEE BELOW)
            self._reconcile_invoices_with_settlement(invoices)

        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        invoices = super()._create_invoices(
            grouped=grouped,
            final=final,
            date=date
        )

        for invoice in invoices:
            sale = invoice.invoice_line_ids.mapped('sale_line_ids.order_id')
            sale = sale[:1]

            if not sale or not sale.is_fuel_sale:
                continue

            invoice.write({
                'is_fuel_invoice': True,
                'fuel_inv_type': sale.fuel_sale_type,
                'shift_manager_id': sale.shift_manager_id.id,
                'nozzle_id': sale.nozzle_id.id,
                'settlement_id': sale.settlement_id.id,
            })

        return invoices

    def _reconcile_invoices_with_settlement(self, invoices):
        AccountPayment = self.env['account.payment']

        for invoice in invoices:
            print("\n========== RECONCILIATION START ==========")
            print(f"Invoice: {invoice.name} | ID: {invoice.id}")

            if (
                    invoice.state != 'posted'
                    or not invoice.settlement_id
                    or not invoice.is_fuel_invoice
                    or invoice.fuel_inv_type not in ('walk', 'loyalty')
            ):
                print("❌ Invoice not eligible")
                continue

            # ------------------------------------------------
            # INVOICE RECEIVABLE LINE
            # ------------------------------------------------
            inv_line = invoice.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                          and not l.reconciled
            )

            if not inv_line:
                print("❌ No receivable line")
                continue

            print(f"✔ Invoice receivable line: {inv_line.ids}")
            print(f"   Residual: {invoice.amount_residual}")

            # ------------------------------------------------
            # PAYMENTS (SHIFT ONLY)
            # ------------------------------------------------
            payments = AccountPayment.search([
                ('state', '=', 'posted'),
                ('settlement_id', '=', invoice.settlement_id.id),
                ('is_petty_cash', '=', False),
                ('amount', '!=', 0.0),
            ])

            print(f"✔ Found payments: {payments.mapped('name')}")

            for pay in payments:
                pay_line = pay.move_id.line_ids.filtered(
                    lambda l: l.account_id == inv_line.account_id
                              and not l.reconciled
                              and l.credit > 0
                )

                if pay_line:
                    print(f"🔥 Reconciling with payment {pay.name}")
                    (inv_line + pay_line).reconcile()

            print("========== RECONCILIATION END ==========\n")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def create(self, vals):
        product_id = vals.get('product_id')
        if product_id:
            product = self.env['product.product'].browse(product_id)
            if product.is_fuel_product and not self.env.context.get('from_fuel_station'):
                raise ValidationError(
                    "Fuel products can only be sold through Fuel Sales / Fuel Station."
                )
        return super().create(vals)

    @api.onchange('product_id')
    def _onchange_product_id_fuel(self):
        if self.env.context.get('from_fuel_station'):
            return {
                'domain': {
                    'product_id': [('is_fuel_product', '=', True)]
                }
            }
