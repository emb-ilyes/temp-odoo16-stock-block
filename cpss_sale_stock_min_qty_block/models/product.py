from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    cpss_block_below_min = fields.Boolean(
        string="Bloquer vente sous stock minimum",
        default=False
    )