# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crm_routing_auto_create = fields.Boolean(
        'Route leads on creation',
        config_parameter='crm_lead_routing.auto_create',
        help='Apply the routing rules to every lead created without a salesperson (incoming email, web forms, imports, integrations).')
