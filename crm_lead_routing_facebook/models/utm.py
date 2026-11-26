# -*- coding: utf-8 -*-
from odoo import api, fields, models


class UtmMedium(models.Model):
    _inherit = 'utm.medium'

    facebook_ad_id = fields.Char('Facebook Ad ID', index='btree_not_null', copy=False)

    _facebook_ad_unique = models.Constraint('unique(facebook_ad_id)', 'This Facebook ad already exists.')

    @api.model
    def _facebook_get_or_create(self, ad_id, name):
        if not ad_id:
            return self.browse()
        return self.search([('facebook_ad_id', '=', ad_id)], limit=1) or \
            self.create({'facebook_ad_id': ad_id, 'name': name or ad_id})


class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'

    facebook_campaign_id = fields.Char('Facebook Campaign ID', index='btree_not_null', copy=False)

    _facebook_campaign_unique = models.Constraint(
        'unique(facebook_campaign_id)', 'This Facebook campaign already exists.')

    @api.model
    def _facebook_get_or_create(self, campaign_id, name):
        if not campaign_id:
            return self.browse()
        return self.search([('facebook_campaign_id', '=', campaign_id)], limit=1) or \
            self.create({'facebook_campaign_id': campaign_id, 'name': name or campaign_id})
