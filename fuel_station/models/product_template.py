from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_fuel_product = fields.Boolean(
        string="Fuel Product",
        help="Enable this for Petrol, Diesel, Oil and other fuel-related products."
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_fuel_product = fields.Boolean(
        related="product_tmpl_id.is_fuel_product",
        store=True,
        readonly=True
    )
