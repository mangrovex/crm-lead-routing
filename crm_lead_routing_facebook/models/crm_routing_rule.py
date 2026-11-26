# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmRoutingRule(models.Model):
    _inherit = 'crm.routing.rule'

    facebook_form_ids = fields.Many2many(
        'crm.facebook.form', 'crm_routing_rule_facebook_form_rel', 'rule_id', 'form_id',
        string='Facebook Forms',
        help='The rule only applies to leads coming from these forms.')

    def _match_extra(self, lead):
        if self.facebook_form_ids and lead.facebook_form_id not in self.facebook_form_ids:
            return False
        return super()._match_extra(lead)
