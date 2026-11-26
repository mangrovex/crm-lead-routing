# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    routing_rule_ids = fields.One2many('crm.routing.rule', 'team_id', 'Routing Rules')
    routing_rule_count = fields.Integer('Rule Count', compute='_compute_routing_rule_count')

    def _compute_routing_rule_count(self):
        groups = self.env['crm.routing.rule']._read_group([('team_id', 'in', self.ids)], ['team_id'], ['__count'])
        counts = {team.id: count for team, count in groups}
        for team in self:
            team.routing_rule_count = counts.get(team.id, 0)

    def action_view_routing_rules(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('crm_lead_routing.action_crm_routing_rule')
        action['domain'] = [('team_id', '=', self.id)]
        action['context'] = {'default_team_id': self.id}
        return action
