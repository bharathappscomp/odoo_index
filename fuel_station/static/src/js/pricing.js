/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class Pricing extends Component {
    static template = "fuel_station.pricing_screen";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            products: [],
            loading: true,
            pricing_date: new Date().toISOString().slice(0, 10),
        });

        onMounted(async () => {
            await this.loadFuelProducts();
        });
    }

    async loadFuelProducts() {
        this.state.loading = true;

        const products = await this.orm.searchRead(
            "product.product",
            [["is_fuel_product", "=", true]],
            ["id", "display_name", "lst_price"]
        );

        this.state.products = products.map(p => ({
            product_id: p.id,
            name: p.display_name,
            price: p.lst_price || 0,
        }));

        this.state.loading = false;
    }

    getProductImageUrl(productId) {
        return `/web/image/product.product/${productId}/image_128`;
    }

    async onDoneClick() {
        if (!this.state.products.length) {
            this.notification.add("No fuel products found", { type: "warning" });
            return;
        }

        // 1️⃣ Create pricing record (ARRAY is mandatory)
        const [pricingId] = await this.orm.create("fuel.pricing", [
            {
                pricing_date: this.state.pricing_date,
                line_ids: this.state.products.map(p => [
                    0, 0, {
                        product_id: p.product_id,
                        price: p.price,
                    }
                ])
            }
        ]);

// 2️⃣ Update product prices
//        for (const p of this.state.products) {
//            await this.orm.write(
//                "product.product",
//                [p.product_id],
//                { lst_price: p.price }
//            );
//        }

        this.notification.add("Fuel prices saved successfully", {
            type: "success",
        });
    }

}

registry.category("actions").add("fuel_station.pricing_screen", Pricing);
