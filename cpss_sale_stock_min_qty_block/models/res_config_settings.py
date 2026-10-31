from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cpss_stock_mode = fields.Selection([
        ('block', 'Blocage strict'),
        ('warning', 'Avertissement seulement'),
    ], string="Mode de contrôle stock",
       config_parameter='cpss.stock_mode')

    cpss_allow_manager_override = fields.Boolean(
        string="Autoriser dépassement par un manager",
        config_parameter='cpss.allow_manager_override'
    )