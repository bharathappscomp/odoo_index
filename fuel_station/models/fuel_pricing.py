from odoo import models, fields, api


class FuelPricing(models.Model):
    _name = "fuel.pricing"
    _description = "Fuel Pricing"

    name = fields.Char(
        string="Reference",
        default=lambda self: self.env['ir.sequence'].next_by_code('fuel.pricing'),
        readonly=True
    )
    pricing_date = fields.Date(
        string="Date",
        default=fields.Date.today
    )

    line_ids = fields.One2many(
        'fuel.pricing.line',
        'pricing_id',
        string="Fuel Prices"
    )

    @api.model
    def create(self, vals):
        print("CREATE called with vals:", vals)

        record = super().create(vals)

        print("Created pricing:", record.id, "date:", record.pricing_date)

        record._apply_today_pricing()
        return record

    def write(self, vals):
        print("WRITE called on IDs:", self.ids, "vals:", vals)

        res = super().write(vals)

        self._apply_today_pricing()
        return res

    def _apply_today_pricing(self):
        today = fields.Date.today()
        print("Apply pricing check. Today:", today)

        for pricing in self:
            print("Checking pricing:", pricing.id, "date:", pricing.pricing_date)

            if pricing.pricing_date == today:
                print("Date matches today. Applying prices.")

                for line in pricing.line_ids:
                    print(
                        "Updating product:",
                        line.product_id.id,
                        "price:",
                        line.price
                    )

                    line.product_id.write({
                        'lst_price': line.price
                    })
            else:
                print("Date does not match. Skipping.")

    def apply_today_pricing_cron(self):
        today = fields.Date.today()
        print("Cron running. Today:", today)

        pricings = self.search([('pricing_date', '=', today)])
        print("Pricings found:", pricings.ids)

        for pricing in pricings:
            for line in pricing.line_ids:
                print(
                    "Cron updating product:",
                    line.product_id.id,
                    "price:",
                    line.price
                )

                line.product_id.write({
                    'lst_price': line.price
                })

class FuelPricingLine(models.Model):
    _name = "fuel.pricing.line"
    _description = "Fuel Pricing Line"

    pricing_id = fields.Many2one(
        'fuel.pricing',
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string="Fuel Product",
        required=True
    )

    price = fields.Float(string="Price", required=True)
