# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError

class ConfirmOverride(models.TransientModel):
    _name = 'cpss.confirm.override'
    _description = 'Confirmation Override'

    message = fields.Text(readonly=True)
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade')

    def action_confirm(self):
        config = self.env['ir.config_parameter'].sudo()
        mode = config.get_param('cpss.stock_mode', 'block')
        allow_override = config.get_param('cpss.allow_manager_override', 'False') == 'True'

        # Security Check: If the system is in strict 'block' mode,
        # ensure the user actually has the manager override group before allowing confirmation.
        if mode == 'block':
            has_group = self.env.user.has_group('cpss_sale_stock_min_qty_block.group_allow_below_min_stock')
            if not (allow_override and has_group):
                raise UserError(_("Vous n'êtes pas autorisé à forcer cette confirmation en mode de blocage strict."))

        # Proceed with forced confirmation
        return self.order_id.with_context(
            cpss_force_confirm=self.order_id.id
        ).action_confirm()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}