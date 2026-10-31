# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cpss_min_qty_alert = fields.Text(
        string="Alerte stock minimum",
        related='sale_id.cpss_min_qty_alert',
        readonly=True,
        help="Alerte de stock minimum portée par le bon de livraison lié à "
             "cette vente (toujours visible dans l'application Inventaire).",
    )
