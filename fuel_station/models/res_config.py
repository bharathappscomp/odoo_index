from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fuel_auto_confirm_sale = fields.Boolean(
        string="Auto Confirm Fuel Sales",
        help="If enabled, Walk-in and Credit Sale Orders will be automatically confirmed while closing the shift."
    )

    fuel_credit_loyalty_allowed = fields.Boolean(
        string="Allow Loyalty on Credit Sales",
        help="If enabled, loyalty points can be applied or earned for Credit Sale customers."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        IrConfig = self.env['ir.config_parameter'].sudo()

        res.update(
            fuel_auto_confirm_sale=IrConfig.get_param(
                'fuel_station.auto_confirm_sale', default=False
            ),
            fuel_credit_loyalty_allowed=IrConfig.get_param(
                'fuel_station.credit_loyalty_allowed', default=False
            )
        )
        return res

    def set_values(self):
        super().set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()

        IrConfig.set_param(
            'fuel_station.auto_confirm_sale',
            self.fuel_auto_confirm_sale
        )
        IrConfig.set_param(
            'fuel_station.credit_loyalty_allowed',
            self.fuel_credit_loyalty_allowed
        )
