from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.sale_loyalty.models.sale_order import SaleOrder as LoyaltySaleOrder
from odoo.tools.float_utils import float_is_zero

class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_reward_applied = fields.Boolean(default=False)

    def action_confirm(self):
        print("=======FUEL STATION LOYALTY action_confirm Inherit=======")

        credit_loyalty_allowed = self.env['ir.config_parameter'].sudo().get_param(
            'fuel_station.credit_loyalty_allowed'
        )

        loyalty_orders = self.filtered(
            lambda o: o.partner_id.is_loyalty_customer and (
                    o.fuel_sale_type == 'loyalty' or
                    (o.fuel_sale_type == 'credit' and credit_loyalty_allowed)
            )
        )

        if loyalty_orders:
            for order in self:
                all_coupons = order.applied_coupon_ids | order.coupon_point_ids.coupon_id | order.order_line.coupon_id
                if any(order._get_real_points_for_coupon(coupon) < 0 for coupon in all_coupons):
                    raise ValidationError(_('One or more rewards on the sale order is invalid. Please check them.'))
                order._update_programs_and_rewards()

            reward_coupons = self.order_line.coupon_id
            self.coupon_point_ids.filtered(
                lambda pe: pe.coupon_id.program_id.applies_on == 'current' and pe.coupon_id not in reward_coupons
            ).coupon_id.sudo().unlink()
            # Add/remove the points to our coupons
            for coupon, change in self.filtered(lambda s: s.state != 'sale')._get_point_changes().items():
                coupon.points += change
            self._send_reward_coupon_mail()

        return super(LoyaltySaleOrder, self).action_confirm()

    @api.model
    def get_loyalty_claimable_rewards(self, partner_id, product_id, qty):
        """
        Return claimable rewards for a loyalty customer
        """
        try:
            qty = float(qty or 0)
        except (TypeError, ValueError):
            qty = 0

        if not partner_id or not product_id or qty <= 0:
            return []

        order = self.with_context(from_fuel_station=True).create({
            "partner_id": partner_id,
            "order_line": [(0, 0, {
                "product_id": product_id,
                "product_uom_qty": qty,
            })],
            "is_fuel_sale": True,
            "fuel_sale_type": "loyalty",
        })

        try:
            order._update_programs_and_rewards()
            claimable = order._get_claimable_rewards()

            rewards = []
            for coupon, reward_set in claimable.items():
                for reward in reward_set:
                    rewards.append({
                        "id": reward.id,
                        "name": reward.description,
                        "required_points": reward.required_points,
                        "coupon_id": coupon.id,
                    })

            return rewards

        finally:
            order.unlink()

    def apply_loyalty_reward(self, reward_id):
        self.ensure_one()

        reward = self.env['loyalty.reward'].browse(reward_id)
        if not reward:
            raise ValidationError(_("Invalid reward selected."))

        self._update_programs_and_rewards()
        claimable = self._get_claimable_rewards()
        selected_coupon = False

        for coupon, rewards in claimable.items():
            if reward in rewards:
                selected_coupon = coupon
                break

        if not selected_coupon:
            raise ValidationError(_("Selected reward is not claimable for this order."))

        self._apply_program_reward(reward, selected_coupon)
        self._update_programs_and_rewards()

        return True