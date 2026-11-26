# -*- coding: utf-8 -*-
from odoo import fields, models

from .crm_facebook_form_field import LEAD_FIELD_DOMAIN


class CrmFacebookFormMapping(models.Model):
    _name = 'crm.facebook.form.mapping'
    _description = 'Default Facebook Field Mapping'

    facebook_field = fields.Char('Facebook Field', required=True)
    odoo_field = fields.Many2one('ir.model.fields', 'Odoo Field', required=True, domain=LEAD_FIELD_DOMAIN,
                                 ondelete='cascade')

    _map_unique = models.Constraint('unique(facebook_field)', 'A mapping already exists for this Facebook field.')
