# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models


class CrmRoutingLog(models.Model):
    _name = 'crm.routing.log'
    _description = 'Lead Routing Log'
    _order = 'date desc, id desc'
    _rec_name = 'lead_id'

    date = fields.Datetime('Date', default=fields.Datetime.now, required=True, index=True)
    lead_id = fields.Many2one('crm.lead', 'Lead', ondelete='set null', index=True)
    rule_id = fields.Many2one('crm.routing.rule', 'Rule', ondelete='set null', index=True)
    team_id = fields.Many2one('crm.team', 'Team', ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', 'Salesperson', ondelete='set null', index=True)
    previous_user_id = fields.Many2one('res.users', 'Previous Salesperson', ondelete='set null')
    campaign_id = fields.Many2one('utm.campaign', 'Campaign', ondelete='set null', index=True)
    channel = fields.Selection(selection='_selection_channel', string='Channel')
    trigger = fields.Selection([
        ('create', 'Creation'),
        ('manual', 'Manual'),
        ('cron', 'Scheduled'),
    ], 'Trigger', default='manual')
    reason = fields.Char('Reason')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    @api.model
    def _selection_channel(self):
        return self.env['crm.lead']._selection_routing_channel()

    @api.model
    def _count_assignments(self, users, team=None, campaign=None, days=0, triggers=None):
        """{user_id: number of logged assignments}.

        ``campaign``: utm.campaign record (empty = no campaign) or None to ignore it.
        ``days``: lookback window (0 = all). ``triggers``: triggers to count.
        """
        if not users:
            return {}
        domain = [('user_id', 'in', users.ids)]
        if team:
            domain.append(('team_id', '=', team.id))
        if campaign is not None:
            domain.append(('campaign_id', '=', campaign.id or False))
        if triggers:
            domain.append(('trigger', 'in', list(triggers)))
        if days:
            domain.append(('date', '>=', fields.Datetime.now() - timedelta(days=days)))
        return {user.id: count for user, count in self.sudo()._read_group(domain, ['user_id'], ['__count'])}

    @api.model
    def _last_assignment(self, users, rule):
        """{user_id: id of the last log line written by the rule}.

        The (sequential) id is used instead of the date because Datetime stores seconds
        and bulk imports log several assignments within the same second."""
        if not users:
            return {}
        groups = self.sudo()._read_group(
            [('user_id', 'in', users.ids), ('rule_id', '=', rule.id)], ['user_id'], ['id:max'])
        return {user.id: last for user, last in groups}
