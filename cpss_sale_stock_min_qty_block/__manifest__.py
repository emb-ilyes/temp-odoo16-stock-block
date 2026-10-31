# -*- coding: utf-8 -*-
{
    "name": "Sale Stock Min Quantity Block",
    "version": "16.0.1.0.0",
    "summary": "Block sale orders if stock goes below minimum quantity",
    "author": "CPSS",
    "license": "AGPL-3",
    "category": "Sales",
    "depends": ["sale_management", "sale_stock", "stock"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",  # Fixed: Added security access
        "views/product_view.xml",
        "views/res_config_settings_view.xml",
        "views/wizard_view.xml",
    ],
    "installable": True,
    "application": False,
}