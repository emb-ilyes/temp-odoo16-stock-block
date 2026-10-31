# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class ConfirmOverride(models.TransientModel):
    _name = 'cpss.confirm.override'
    _description = 'Confirmation Override'

    message = fields.Text(readonly=True)
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')

    def action_confirm(self):
        order = self.order_id

        # Security check: in strict blockage mode, only users holding the
        # bypass right (override setting enabled + bypass group) may force
        # the confirmation. In warning mode anyone may proceed (everyone was
        # already warned by this wizard).
        if order._cpss_get_stock_mode() == 'block' and not order._cpss_has_bypass_right():
            raise UserError(_(
                "Vous n'êtes pas autorisé à forcer cette confirmation "
                "en mode de blocage strict."
            ))

        # Proceed with the forced confirmation. sale.order.action_confirm
        # re-checks the rights server-side (a forged context cannot bypass
        # the blockage) and warns stock personnel afterwards.
        return order.with_context(
            cpss_force_confirm=order.id
        ).action_confirm()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
