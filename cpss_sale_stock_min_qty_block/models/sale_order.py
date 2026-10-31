# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError
from collections import defaultdict


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # ✅ BYPASS validation when coming from the override/warning wizard
        if self.env.context.get('cpss_force_confirm') in self.ids:
            res = super().action_confirm()
            # Post an audit log to the chatter
            for order in self:
                order.message_post(body=_(
                    "La vente a été confirmée malgré l'alerte de stock minimum (Validation validée via l'assistant)."
                ))
            return res

        config = self.env['ir.config_parameter'].sudo()
        mode = config.get_param('cpss.stock_mode', 'block')
        allow_override = config.get_param('cpss.allow_manager_override', 'False') == 'True'
        user = self.env.user

        for order in self:
            storable_lines = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.type == 'product' and not l.display_type
            )
            if not storable_lines or not order.warehouse_id:
                continue

            # Group quantities by product to handle duplicate lines correctly
            # and convert to the product's default UoM
            product_qties = defaultdict(float)
            for line in storable_lines:
                qty_in_product_uom = line.product_uom._compute_quantity(
                    line.product_uom_qty, line.product_id.uom_id
                )
                product_qties[line.product_id] += qty_in_product_uom

            # Batch query active reordering rules for all order products to optimize performance
            product_ids = storable_lines.mapped('product_id')
            orderpoints = self.env['stock.warehouse.orderpoint'].search([
                ('product_id', 'in', product_ids.ids),
                ('warehouse_id', '=', order.warehouse_id.id),
                ('active', '=', True)
            ])

            # Map each product to its active minimum quantity
            product_to_min_qty = defaultdict(float)
            for op in orderpoints:
                if op.product_min_qty > product_to_min_qty[op.product_id]:
                    product_to_min_qty[op.product_id] = op.product_min_qty

            # Evaluate product thresholds
            violating_products = []
            for product, qty_to_sell in product_qties.items():
                if product.cpss_block_below_min and product in product_to_min_qty:
                    min_qty = product_to_min_qty[product]

                    # Fetch virtual available in the correct warehouse context
                    virtual_available = product.with_context(warehouse=order.warehouse_id.id).virtual_available
                    forecasted_after_sale = virtual_available - qty_to_sell

                    if forecasted_after_sale < min_qty:
                        violating_products.append(
                            f"- {product.display_name} (Stock prévu: {forecasted_after_sale:.2f}, Minimum requis: {min_qty:.2f})"
                        )

            if violating_products:
                msg = _("Les articles suivants descendent sous le stock minimum autorisé :\n") + "\n".join(
                    violating_products)

                # --- Path 3: Warn only mode (wizard for everyone) ---
                if mode == 'warning':
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Avertissement - Stock Minimum'),
                        'res_model': 'cpss.confirm.override',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_order_id': order.id,
                            'default_message': msg,
                        }
                    }

                # --- Paths 1 & 2: Strict block mode ---
                elif mode == 'block':
                    # If manager bypass is active and the user belongs to the authorized group, trigger wizard
                    if allow_override and user.has_group('cpss_sale_stock_min_qty_block.group_allow_below_min_stock'):
                        return {
                            'type': 'ir.actions.act_window',
                            'name': _('Validation sous stock minimum (Dérogation Manager)'),
                            'res_model': 'cpss.confirm.override',
                            'view_mode': 'form',
                            'target': 'new',
                            'context': {
                                'default_order_id': order.id,
                                'default_message': msg,
                            }
                        }
                    # Otherwise, hard block (either for normal users, or because bypass is turned off entirely)
                    else:
                        raise UserError(_("Stock insuffisant : vous ne pouvez pas confirmer cette vente.\n\n%s") % msg)

        # Confirm the sale order normally if there are no violations
        return super().action_confirm()