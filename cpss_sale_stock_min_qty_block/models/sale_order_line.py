# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cpss_min_qty_warning = fields.Text(
        string="Alerte stock minimum",
        compute='_cpss_compute_min_qty_warning',
        help="Affichée dès la saisie de la quantité, à côté de l'indicateur "
             "de disponibilité d'Odoo, tant que la commande n'est pas "
             "confirmée.",
    )
    cpss_min_qty_severity = fields.Selection(
        selection=[
            ('warning', 'Avertissement'),
            ('block', 'Blocage'),
        ],
        compute='_cpss_compute_min_qty_warning',
        help="Colore la ligne : avertissement (warning) ou blocage (block).",
    )

    @api.depends(
        'product_id', 'product_uom', 'product_uom_qty', 'display_type',
        'product_id.cpss_block_below_min',
        'order_id.warehouse_id',
        'order_id.order_line',
        'order_id.order_line.product_id',
        'order_id.order_line.product_uom',
        'order_id.order_line.product_uom_qty',
        'order_id.order_line.display_type',
    )
    def _cpss_compute_min_qty_warning(self):
        """Live per-line message, evaluated as soon as a quantity is entered
        (before the quotation is saved), next to Odoo's availability widget."""
        for line in self:
            line.cpss_min_qty_warning = False
            line.cpss_min_qty_severity = False
            if line.display_type or not line.product_id or not line.order_id:
                continue
            if not line.product_id.cpss_block_below_min:
                continue

            violation = line.order_id._cpss_order_violations().get(line.product_id)
            if not violation:
                continue

            forecasted_after_sale, min_qty = violation
            line.cpss_min_qty_warning = _(
                "Stock sous le minimum : prévu %.2f / minimum %.2f"
            ) % (forecasted_after_sale, min_qty)

            if (line.order_id._cpss_get_stock_mode() == 'block'
                    and not line.order_id._cpss_has_bypass_right()):
                line.cpss_min_qty_severity = 'block'
            else:
                line.cpss_min_qty_severity = 'warning'

    @api.constrains('product_id', 'product_uom', 'product_uom_qty')
    def _cpss_check_below_min_on_save(self):
        """Strict blockage: a line cannot be recorded below the minimum
        stock while the quotation is being prepared (draft/sent), unless the
        user holds the bypass right.

        In an editable list a line is written as soon as its row is left, so
        this blocks the quantity at entry time — before the quotation is
        even saved — instead of only at confirmation.
        """
        for line in self:
            if line.display_type or not line.product_id or not line.order_id:
                continue
            order = line.order_id
            if order.state not in ('draft', 'sent'):
                continue
            if order._cpss_get_stock_mode() != 'block':
                continue
            if order._cpss_has_bypass_right():
                continue

            violations = order._cpss_order_violations()
            if line.product_id not in violations:
                continue

            raise ValidationError(_(
                "Stock insuffisant : vous ne pouvez pas enregistrer cette "
                "commande sous le stock minimum.\n\n%s"
            ) % order._cpss_violations_message(violations))
