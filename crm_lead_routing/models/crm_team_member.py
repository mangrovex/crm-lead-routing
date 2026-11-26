# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmTeamMember(models.Model):
    """Extend native sales team members with routing data.

    Reused from Odoo: ``assignment_optout`` (pause assignment) and
    ``assignment_max`` / ``lead_month_count`` (30-day capacity).
    """
    _inherit = 'crm.team.member'

    routing_expertise_ids = fields.Many2many(
        'crm.routing.expertise', 'crm_team_member_routing_expertise_rel', 'member_id', 'expertise_id',
        string='Expertise')
    routing_weight = fields.Integer(
        'Routing Weight', default=1,
        help='Share of leads received compared to teammates with the "Balanced" and "Lowest workload" methods. A weight of 2 receives twice as many as a weight of 1.')
    routing_unavailable_from = fields.Date('Unavailable from')
    routing_unavailable_until = fields.Date('Unavailable until')
    routing_max_open_leads = fields.Integer(
        'Max. Open Leads', default=0,
        help='Maximum number of open leads/opportunities for the salesperson. 0 = unlimited.')
    routing_open_lead_count = fields.Integer('Open Leads', compute='_compute_routing_open_lead_count')
    routing_is_available = fields.Boolean('Available Today', compute='_compute_routing_is_available')

    _routing_weight_positive = models.Constraint('CHECK(routing_weight > 0)', 'The weight must be greater than zero.')
    _routing_max_open_positive = models.Constraint(
        'CHECK(routing_max_open_leads >= 0)', 'The maximum of open leads cannot be negative.')

    @api.constrains('routing_unavailable_from', 'routing_unavailable_until')
    def _check_routing_dates(self):
        for member in self:
            if member.routing_unavailable_from and member.routing_unavailable_until \
                    and member.routing_unavailable_from > member.routing_unavailable_until:
                raise ValidationError(self.env._('"Unavailable from" must be earlier than "Unavailable until".'))

    @api.depends('active', 'assignment_optout', 'routing_unavailable_from', 'routing_unavailable_until',
                 'user_id.active')
    def _compute_routing_is_available(self):
        today = fields.Date.context_today(self)
        for member in self:
            member.routing_is_available = member._routing_available_on(today)

    def _routing_available_on(self, date):
        self.ensure_one()
        if not self.active or self.assignment_optout or not self.user_id.active:
            return False
        start, end = self.routing_unavailable_from, self.routing_unavailable_until
        if start and start <= date and (not end or date <= end):
            return False
        if not start and end and date <= end:
            return False
        return True

    @api.model
    def _routing_open_lead_domain(self):
        """Leads counted as open workload."""
        return [('active', '=', True), ('won_status', '=', 'pending')]

    @api.model
    def _routing_open_lead_counts(self, users):
        """{user_id: number of open leads} of the salesperson in any team."""
        if not users:
            return {}
        groups = self.env['crm.lead'].sudo()._read_group(
            self._routing_open_lead_domain() + [('user_id', 'in', users.ids)], ['user_id'], ['__count'])
        return {user.id: count for user, count in groups}

    @api.depends('user_id')
    def _compute_routing_open_lead_count(self):
        counts = self._routing_open_lead_counts(self.user_id)
        for member in self:
            member.routing_open_lead_count = counts.get(member.user_id.id, 0)

    def _routing_has_capacity(self, open_counts):
        """Native 30-day capacity and max. open leads, each one only when set."""
        self.ensure_one()
        if self.assignment_max and self.lead_month_count >= self.assignment_max:
            return False
        if self.routing_max_open_leads and open_counts.get(self.user_id.id, 0) >= self.routing_max_open_leads:
            return False
        return True

    def action_routing_view_open_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Open leads of %s', self.user_id.name),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': self._routing_open_lead_domain() + [('user_id', '=', self.user_id.id)],
            'context': {'create': False},
        }
