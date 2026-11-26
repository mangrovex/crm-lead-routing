# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmFacebookAdset(models.Model):
    _name = 'crm.facebook.adset'
    _description = 'Facebook Ad Set'

    name = fields.Char('Ad Set', required=True)
    facebook_adset_id = fields.Char('Ad Set ID', required=True, index=True)

    _facebook_adset_unique = models.Constraint(
        'unique(facebook_adset_id)', 'This Facebook ad set already exists.')

    @api.model
    def _facebook_get_or_create(self, adset_id, name):
        if not adset_id:
            return self.browse()
        return self.search([('facebook_adset_id', '=', adset_id)], limit=1) or \
            self.create({'facebook_adset_id': adset_id, 'name': name or adset_id})
