# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmRoutingExpertise(models.Model):
    _name = 'crm.routing.expertise'
    _description = 'Sales Expertise Area'
    _order = 'name'

    name = fields.Char('Expertise', required=True, translate=True)
    color = fields.Integer('Color')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('unique(name)', 'This expertise area already exists.')
