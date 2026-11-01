# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cpss_min_qty_alert = fields.Text(
        string="Alerte stock minimum",
        readonly=True,
        copy=False,
        help="Alerte enregistrée lorsque la vente a été confirmée alors que "
             "le stock prévisionnel descendait sous le stock minimum.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _cpss_get_stock_mode(self):
        """Configured control mode: 'warning' or 'block'.

        Unknown values fall back to the safe default: strict blockage.
        """
        mode = self.env['ir.config_parameter'].sudo().get_param('cpss.stock_mode', 'block')
        return mode if mode in ('warning', 'block') else 'block'

    def _cpss_has_bypass_right(self):
        """Bypass right = the manager override setting is enabled AND the
        current user belongs to the bypass group."""
        allow_override = (
            self.env['ir.config_parameter'].sudo()
            .get_param('cpss.allow_manager_override', 'False') == 'True'
        )
        return allow_override and self.env.user.has_group(
            'cpss_sale_stock_min_qty_block.group_allow_below_min_stock'
        )

    def _cpss_get_below_min_messages(self):
        """Return ``{order_id: message}`` for the orders of ``self`` whose
        confirmation would bring the forecasted stock below the minimum."""
        messages = {}
        for order in self:
            storable_lines = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.type == 'product' and not l.display_type
            )
            if not storable_lines or not order.warehouse_id:
                continue

            # Group quantities by product (to handle duplicate lines) and
            # convert them to the product's default UoM
            product_qties = defaultdict(float)
            for line in storable_lines:
                qty_in_product_uom = line.product_uom._compute_quantity(
                    line.product_uom_qty, line.product_id.uom_id
                )
                product_qties[line.product_id] += qty_in_product_uom

            # Batch query the active reordering rules of the order products.
            # sudo() is required: reordering rules are only readable by the
            # stock groups, and the check must run for every account type
            # (a plain sales user would otherwise get an AccessError).
            product_ids = storable_lines.mapped('product_id')
            orderpoints = self.env['stock.warehouse.orderpoint'].sudo().search([
                ('product_id', 'in', product_ids.ids),
                ('warehouse_id', '=', order.warehouse_id.id),
                ('company_id', '=', order.company_id.id),
                ('active', '=', True),
            ])

            # Map each product to its active minimum quantity
            product_to_min_qty = defaultdict(float)
            for op in orderpoints:
                if op.product_min_qty > product_to_min_qty[op.product_id]:
                    product_to_min_qty[op.product_id] = op.product_min_qty

            # Evaluate the product thresholds
            violating_lines = []
            for product, qty_to_sell in product_qties.items():
                if product.cpss_block_below_min and product in product_to_min_qty:
                    min_qty = product_to_min_qty[product]

                    # Fetch virtual available in the correct warehouse context
                    virtual_available = product.with_context(
                        warehouse=order.warehouse_id.id
                    ).virtual_available
                    forecasted_after_sale = virtual_available - qty_to_sell

                    if forecasted_after_sale < min_qty:
                        violating_lines.append(
                            "- %s (Stock prévu: %.2f, Minimum requis: %.2f)"
                            % (product.display_name, forecasted_after_sale, min_qty)
                        )

            if violating_lines:
                messages[order.id] = (
                    _("Les articles suivants descendent sous le stock minimum autorisé :\n%s")
                    % "\n".join(violating_lines)
                )
        return messages

    def _cpss_open_override_wizard(self, message, title):
        """Display the warning/override wizard for this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'cpss.confirm.override',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_message': message,
            },
        }

    def _cpss_warn_stock_users(self, message):
        """Warn stock personnel after a sale confirmed below minimum stock.

        * The alert is persisted on the sale order (warning banner).
        * An audit note is posted on the sale order chatter.
        * Every stock user is notified on the related pickings: in Inventory
          the warning is always shown (banner + chatter note).
        """
        self.ensure_one()
        body = _("Vente confirmée malgré l'alerte de stock minimum.\n\n%s") % message

        # Persist the alert on the sale order (banner in the sales form)
        self.cpss_min_qty_alert = body

        # Audit note on the sale order for its followers
        self.message_post(body=body)

        # Stock personnel to warn (Inventory users and managers), searched
        # with sudo so the notification works for every confirming account
        # type.
        stock_groups = (
            self.env.ref('stock.group_stock_user')
            | self.env.ref('stock.group_stock_manager')
        )
        stock_users = self.env['res.users'].sudo().search([
            ('groups_id', 'in', stock_groups.ids),
            ('active', '=', True),
        ])
        stock_partners = stock_users.partner_id

        if self.picking_ids:
            # In Inventory the warning is always shown on every related
            # picking, and stock personnel are notified there (they usually
            # have no read access on sale orders).
            for picking in self.picking_ids:
                picking.sudo().message_post(
                    body=body,
                    author_id=self.env.user.partner_id.id,
                    partner_ids=stock_partners.ids,
                )
        else:
            # No picking to carry the warning: notify stock personnel
            # directly on the sale order.
            self.message_post(body=body, partner_ids=stock_partners.ids)

    # ------------------------------------------------------------------
    # Confirmation flow
    # ------------------------------------------------------------------
    def action_confirm(self):
        violations = self._cpss_get_below_min_messages()
        forced = bool(self.env.context.get('cpss_force_confirm'))

        if violations:
            mode = self._cpss_get_stock_mode()
            has_bypass = self._cpss_has_bypass_right()
            first = next(order for order in self if order.id in violations)
            block_message = _(
                "Stock insuffisant : vous ne pouvez pas confirmer cette vente.\n\n%s"
            ) % violations[first.id]

            if forced:
                # The force flag comes from the override wizard; the rights
                # are re-checked server-side so that a forged context can
                # never bypass a strict blockage.
                if mode == 'block' and not has_bypass:
                    raise UserError(block_message)
            elif mode == 'warning':
                # Warning mode: warn every user, whatever their account type.
                return first._cpss_open_override_wizard(
                    violations[first.id],
                    _('Avertissement - Stock Minimum'),
                )
            elif mode == 'block' and has_bypass:
                # Strict blockage + bypass right: warn the user first, then
                # let them confirm.
                return first._cpss_open_override_wizard(
                    violations[first.id],
                    _('Validation sous stock minimum (Dérogation Manager)'),
                )
            else:
                # Strict blockage without bypass right: hard block.
                raise UserError(block_message)

        res = super().action_confirm()

        # A confirmation that reaches this point with violations went through
        # the override wizard (warning mode, or blockage bypassed by an
        # authorized user): warn stock personnel in all cases.
        for order in self:
            if order.id in violations:
                order._cpss_warn_stock_users(violations[order.id])

        return res
