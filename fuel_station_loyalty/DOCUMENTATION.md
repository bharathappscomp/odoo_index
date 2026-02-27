# Fuel Station Loyalty — Full Documentation

## Overview

**Fuel Station Loyalty** is an Odoo module that extends the standard Odoo Loyalty (`sale_loyalty`) system to support fuel station operations. It integrates with the **Advance Fuel Station Management System** (`fuel_station`) to provide loyalty rewards and point redemption for fuel sales.

---

## Table of Contents

1. [Module Information](#module-information)
2. [Dependencies](#dependencies)
3. [Architecture](#architecture)
4. [Features](#features)
5. [Technical Implementation](#technical-implementation)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [API Reference](#api-reference)
9. [Views & UI](#views--ui)
10. [Integration with Fuel Station](#integration-with-fuel-station)
11. [Installation](#installation)
12. [Troubleshooting](#troubleshooting)

---

## Module Information

| Property | Value |
|----------|-------|
| **Name** | Fuel Station Loyalty |
| **Technical Name** | `fuel_station_loyalty` |
| **Version** | 17.0.0.0.0 |
| **License** | LGPL-3 |
| **Application** | Yes |
| **Sequence** | 1 |

---

## Dependencies

The module depends on the following Odoo modules:

| Module | Purpose |
|--------|---------|
| `base` | Core Odoo framework |
| `web` | Web interface |
| `hr` | Human Resources (for employee-related features) |
| `stock` | Inventory management |
| `sale` | Sales management |
| `account` | Accounting |
| `product` | Product catalog |
| `sale_loyalty` | Odoo standard loyalty & rewards |
| `purchase` | Purchase management |
| `contacts` | Contact/partner management |

**Note:** This module is a dependency of the **Advance Fuel Station Management System** (`fuel_station`). The fuel station module adds `fuel_sale_type`, `is_fuel_sale`, and `is_loyalty_customer` fields that this module relies on.

---

## Architecture

### Module Structure

```
fuel_station_loyalty/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale.py          # Sale order loyalty extensions
├── views/
│   └── sale.xml         # Sale order form view inheritance
└── static/
    └── description/
        └── index.html   # App store / OCA description page
```

### Inheritance Chain

```
sale.order (base)
    └── sale_loyalty.models.sale_order.SaleOrder
        └── fuel_station_loyalty.models.sale.SaleOrder
```

---

## Features

### 1. **Loyalty Order Confirmation**

When a sale order is confirmed, the module applies special logic for **loyalty** and **credit** fuel sales:

- **Loyalty orders** (`fuel_sale_type == 'loyalty'`): Full loyalty point calculation and reward application
- **Credit orders** (`fuel_sale_type == 'credit'`): Loyalty logic applies only if `fuel_station.credit_loyalty_allowed` is enabled

### 2. **Claimable Rewards Lookup**

Provides an API to fetch claimable rewards for a loyalty customer based on:
- Partner (customer) ID
- Product ID
- Quantity

Used by the Fuel Station User Screen when processing loyalty sales.

### 3. **Reward Application**

Allows applying a selected loyalty reward to a sale order, with validation that the reward is claimable for the current order.

### 4. **Reward Validation**

On order confirmation, validates that all applied rewards have non-negative points before allowing confirmation.

---

## Technical Implementation

### Models

#### `sale.order` (inherited)

| Field | Type | Description |
|-------|------|-------------|
| `is_reward_applied` | Boolean | Tracks whether a reward has been applied (default: False) |

### Key Methods

#### `action_confirm()`

Overrides the standard sale order confirmation to:

1. Read `fuel_station.credit_loyalty_allowed` system parameter
2. Filter orders that are loyalty-eligible:
   - Partner must have `is_loyalty_customer == True`
   - Order must be `fuel_sale_type == 'loyalty'` OR (`fuel_sale_type == 'credit'` AND credit loyalty allowed)
3. For loyalty orders:
   - Validate all coupons have non-negative points
   - Update programs and rewards
   - Remove unused "current" program coupons
   - Apply point changes to coupons
   - Send reward coupon emails
4. Call parent `action_confirm()`

#### `get_loyalty_claimable_rewards(partner_id, product_id, qty)`

**Purpose:** Returns claimable rewards for a loyalty customer without creating a permanent order.

**Parameters:**
- `partner_id` (int): Customer/partner ID
- `product_id` (int): Product ID (typically fuel product)
- `qty` (float): Quantity

**Returns:** List of dicts:
```python
[
    {
        "id": reward.id,
        "name": reward.description,
        "required_points": reward.required_points,
        "coupon_id": coupon.id,
    },
    ...
]
```

**Behavior:**
- Creates a temporary sale order with `from_fuel_station=True`, `is_fuel_sale=True`, `fuel_sale_type='loyalty'`
- Calls `_update_programs_and_rewards()` and `_get_claimable_rewards()`
- Deletes the temporary order
- Returns formatted reward list

#### `apply_loyalty_reward(reward_id)`

**Purpose:** Applies a selected loyalty reward to the current sale order.

**Parameters:**
- `reward_id` (int): ID of the `loyalty.reward` to apply

**Raises:** `ValidationError` if reward is invalid or not claimable.

**Behavior:**
- Validates reward exists
- Refreshes claimable rewards
- Finds the coupon that contains the reward
- Applies the reward via `_apply_program_reward()`
- Updates programs and rewards again

---

## Configuration

### System Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `fuel_station.credit_loyalty_allowed` | Allow loyalty points/rewards on credit sales | False |

This parameter is defined in the `fuel_station` module (`res_config.py`). When `True`, credit sales for loyalty customers will also trigger loyalty point calculation and reward handling.

---

## Usage

### From Fuel Station User Screen

1. **Loyalty Sales Dialog**
   - User selects a loyalty customer
   - Enters quantity (fuel volume)
   - Toggles "Redeem" to use a reward
   - Backend calls `get_loyalty_claimable_rewards(partner_id, product_id, qty)` to populate reward dropdown
   - User selects a reward and saves
   - On order creation/confirmation, `apply_loyalty_reward(reward_id)` is used (or rewards are applied via standard flow)

2. **Order Confirmation**
   - When a loyalty or credit (if allowed) order is confirmed, the module automatically:
     - Validates rewards
     - Updates loyalty points
     - Sends reward emails

### From Python/XML-RPC

```python
# Get claimable rewards for a customer
rewards = env['sale.order'].get_loyalty_claimable_rewards(
    partner_id=123,
    product_id=456,
    qty=50.0
)

# Apply a reward to an order
order = env['sale.order'].browse(789)
order.apply_loyalty_reward(reward_id=10)
```

---

## API Reference

### Public Methods

| Method | Description |
|-------|-------------|
| `get_loyalty_claimable_rewards(partner_id, product_id, qty)` | Returns claimable rewards for a loyalty customer |
| `apply_loyalty_reward(reward_id)` | Applies a loyalty reward to the current order |

### Context Keys

| Key | Purpose |
|-----|---------|
| `from_fuel_station` | Indicates the order was created from the fuel station interface |
| `is_fuel_sale` | Marks the order as a fuel sale |
| `fuel_sale_type` | One of: `'walk'`, `'credit'`, `'loyalty'` |

---

## Views & UI

### Sale Order Form

The module adds an invisible field to the sale order form:

- **Field:** `is_reward_applied`
- **Position:** After `payment_term_id`
- **Visibility:** Invisible (used for logic/tracking)

**File:** `views/sale.xml`

```xml
<xpath expr="//field[@name='payment_term_id']" position="after">
    <field name="is_reward_applied" invisible="1"/>
</xpath>
```

---

## Integration with Fuel Station

The Fuel Station module (`fuel_station`) depends on `fuel_station_loyalty` and provides:

1. **Fields on `sale.order`:**
   - `is_fuel_sale` (Boolean)
   - `fuel_sale_type` (Selection: walk, credit, loyalty)

2. **Fields on `res.partner`:**
   - `is_loyalty_customer` (Boolean)

3. **User Screen Loyalty Dialog:**
   - Uses `get_loyalty_claimable_rewards` when user toggles "Redeem" for a loyalty line
   - Displays available rewards in a dropdown
   - Saves selected reward for application on order confirmation

4. **Configuration:**
   - `fuel_station.credit_loyalty_allowed` — whether credit sales get loyalty treatment

---

## Installation

### Prerequisites

- Odoo 17.0 (or compatible version with `sale_loyalty`)
- Advance Fuel Station Management System (recommended for full functionality)

### Steps

1. Place the `fuel_station_loyalty` module in your Odoo addons path
2. Update the apps list: **Apps → Update Apps List**
3. Install **Fuel Station Loyalty** from the Apps menu
4. If using fuel station features, install **Advance Fuel Station Management System** (it will pull this module as a dependency)

### Standalone vs. With Fuel Station

- **Standalone:** The module installs and extends `sale.order` with loyalty logic. Without `fuel_station`, the `action_confirm` override will not match any orders (no `fuel_sale_type`/`is_loyalty_customer`), so behavior is equivalent to standard `sale_loyalty`.
- **With Fuel Station:** Full integration for loyalty and credit fuel sales with reward redemption.

---

## Troubleshooting

### "One or more rewards on the sale order is invalid"

- **Cause:** A coupon has negative points when the order is confirmed.
- **Action:** Review loyalty programs and ensure rewards are correctly configured. Check that customers have sufficient points before applying rewards.

### "Invalid reward selected"

- **Cause:** `apply_loyalty_reward` was called with a non-existent or invalid reward ID.
- **Action:** Ensure the reward ID exists and belongs to an active loyalty program.

### "Selected reward is not claimable for this order"

- **Cause:** The reward does not meet the conditions for the current order (e.g., product, quantity, or points).
- **Action:** Re-fetch claimable rewards with `get_loyalty_claimable_rewards` and only offer those rewards to the user.

### Loyalty not applied on credit sales

- **Cause:** `fuel_station.credit_loyalty_allowed` is `False`.
- **Action:** Enable "Credit Loyalty Allowed" in Fuel Station configuration (Settings → Fuel Station).

### No rewards shown in Loyalty Dialog

- **Cause:** Customer has no claimable rewards for the given product/quantity, or loyalty programs are misconfigured.
- **Action:** Verify loyalty programs, rules, and rewards. Ensure the product and quantity qualify for at least one reward.

---

## Changelog

| Version | Notes |
|---------|-------|
| 17.0.0.0.0 | Initial release. Loyalty integration for fuel station sales. |

---

## Related Documentation

- [Odoo Loyalty Documentation](https://www.odoo.com/documentation/17.0/applications/sales/loyalty.html)
- Advance Fuel Station Management System — User Guide (see `fuel_station` module)

---

*Documentation generated for Fuel Station Loyalty module. Last updated: February 2025.*
