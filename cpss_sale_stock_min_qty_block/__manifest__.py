# -*- coding: utf-8 -*-
{
    "name": "Sale Stock Min Quantity Block",
    "version": "16.0.1.1.0",
    "summary": "Block sale orders if stock goes below minimum quantity",
    "author": "CPSS",
    "license": "AGPL-3",
    "category": "Sales",
    "depends": ["sale_management", "sale_stock", "stock"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/product_view.xml",
        "views/res_config_settings_view.xml",
        "views/wizard_view.xml",
        "views/sale_order_view.xml",
        "views/stock_picking_view.xml",
    ],
    "installable": True,
    "application": False,
}
