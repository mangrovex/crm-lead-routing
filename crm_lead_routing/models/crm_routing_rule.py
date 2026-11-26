# -*- coding: utf-8 -*-
import logging
import unicodedata
from ast import literal_eval
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def normalize_text(text):
    """Lowercase without accents: ' Bogotá' == 'bogota'."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text.strip().lower())
    return ''.join(c for c in text if not unicodedata.combining(c))


class CrmRoutingRule(models.Model):
    _name = 'crm.routing.rule'
    _description = 'Lead Routing Rule'
    _order = 'sequence, id'

    name = fields.Char('Rule', required=True)
    sequence = fields.Integer('Priority', default=10,
                              help='Rules are evaluated in this order; the first matching rule assigns.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    note = fields.Text('Notes')

    # ------------------------------------------------------------------
    # Criteria (empty = any). All defined criteria must match; within a
    # criterion any of its values is enough.
    # ------------------------------------------------------------------
    channel = fields.Selection(selection='_selection_channel', string='Channel')
    lead_type = fields.Selection([('lead', 'Lead'), ('opportunity', 'Opportunity')], 'Type')
    country_ids = fields.Many2many('res.country', 'crm_routing_rule_country_rel', 'rule_id', 'country_id',
                                   string='Countries')
    state_ids = fields.Many2many('res.country.state', 'crm_routing_rule_state_rel', 'rule_id', 'state_id',
                                 string='States')
    city_names = fields.Char(
        'Cities', help='Comma-separated list, case and accent insensitive. e.g. Austin, Dallas, Houston')
    industry_ids = fields.Many2many('res.partner.industry', 'crm_routing_rule_industry_rel', 'rule_id',
                                    'industry_id', string='Industries')
    tag_ids = fields.Many2many('crm.tag', 'crm_routing_rule_tag_rel', 'rule_id', 'tag_id', string='Tags')
    campaign_ids = fields.Many2many('utm.campaign', 'crm_routing_rule_campaign_rel', 'rule_id', 'campaign_id',
                                    string='Campaigns')
    source_ids = fields.Many2many('utm.source', 'crm_routing_rule_source_rel', 'rule_id', 'source_id',
                                  string='Sources')
    medium_ids = fields.Many2many('utm.medium', 'crm_routing_rule_medium_rel', 'rule_id', 'medium_id',
                                  string='Mediums')
    domain = fields.Char('Advanced Filter', default='[]',
                         help='Additional domain on crm.lead, e.g. [("expected_revenue", ">", 5000)]')

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------
    team_id = fields.Many2one('crm.team', 'Target Team', required=True, ondelete='cascade',
                              domain="['|', ('use_leads', '=', True), ('use_opportunities', '=', True)]")
    assign_method = fields.Selection(selection='_selection_assign_method', string='Assignment Method',
                                     required=True, default='balanced')
    expertise_ids = fields.Many2many(
        'crm.routing.expertise', 'crm_routing_rule_expertise_rel', 'rule_id', 'expertise_id',
        string='Required Expertise',
        help='Only team members having ALL these expertise areas are considered.')
    respect_capacity = fields.Boolean(
        'Respect Capacity', default=True,
        help='Skip salespeople who reached their 30-day capacity or their maximum of open leads.')
    balance_window_days = fields.Integer(
        'Balancing Window (days)', default=30,
        help='Days back counted by the "Balanced" method. 0 = full history.')
    balance_by_campaign = fields.Boolean(
        'Balance per campaign',
        help='With "Balanced", only count assignments of the same campaign as the lead.')
    fallback = fields.Selection([
        ('leader', 'Assign to the team leader'),
        ('unassigned', 'Leave without salesperson (team only)'),
    ], 'If no salesperson is eligible', required=True, default='leader')

    log_ids = fields.One2many('crm.routing.log', 'rule_id', 'Assignments')
    log_count = fields.Integer('Assignment Count', compute='_compute_log_count')
    eligible_member_ids = fields.Many2many('crm.team.member', compute='_compute_eligible_member_ids',
                                           string='Eligible Salespeople Today')

    # ------------------------------------------------------------------
    # Extensible selections
    # ------------------------------------------------------------------
    @api.model
    def _selection_channel(self):
        return self.env['crm.lead']._selection_routing_channel()

    @api.model
    def _selection_assign_method(self):
        """Extend with super() to add methods; implement ``_pick_<method>``."""
        _ = self.env._
        labels = {
            'leader': _('Team leader'),
            'round_robin': _('Round robin (rotation)'),
            'balanced': _('Balanced (fewest assignments received)'),
            'least_loaded': _('Lowest workload (open leads)'),
            'top_performer': _('Top performer (won last month)'),
            'top_invoiced': _('Top seller by invoicing (last month)'),
            'team_only': _('Team only (no salesperson)'),
        }
        return list(labels.items())

    @api.constrains('domain')
    def _check_domain(self):
        for rule in self:
            try:
                self.env['crm.lead'].search_count(literal_eval(rule.domain or '[]'), limit=1)
            except Exception as exc:
                raise ValidationError(self.env._(
                    'The advanced filter of rule "%(rule)s" is not valid: %(error)s',
                    rule=rule.name, error=exc))

    def _compute_log_count(self):
        groups = self.env['crm.routing.log']._read_group([('rule_id', 'in', self.ids)], ['rule_id'], ['__count'])
        counts = {rule.id: count for rule, count in groups}
        for rule in self:
            rule.log_count = counts.get(rule.id, 0)

    @api.depends('team_id', 'expertise_ids', 'respect_capacity')
    def _compute_eligible_member_ids(self):
        for rule in self:
            rule.eligible_member_ids = rule._get_eligible_members() if rule.team_id else False

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------
    @api.model
    def _find_rule(self, lead):
        """First active rule (by priority) matching the lead."""
        company = lead.company_id or self.env.company
        for rule in self.search([('company_id', 'in', [False, company.id])]):
            try:
                if rule._match(lead):
                    return rule
            except Exception:
                _logger.exception('Error evaluating routing rule %s for lead %s',
                                  rule.display_name, lead.id)
        return self.browse()

    def _match(self, lead):
        self.ensure_one()
        if self.channel and lead.routing_channel != self.channel:
            return False
        if self.lead_type and lead.type != self.lead_type:
            return False
        if self.country_ids and lead.country_id not in self.country_ids:
            return False
        if self.state_ids and lead.state_id not in self.state_ids:
            return False
        if self.city_names:
            cities = {normalize_text(c) for c in self.city_names.split(',') if c.strip()}
            if normalize_text(lead.city) not in cities:
                return False
        if self.industry_ids:
            industry = lead.industry_id or lead.partner_id.commercial_partner_id.industry_id
            if industry not in self.industry_ids:
                return False
        if self.tag_ids and not (lead.tag_ids & self.tag_ids):
            return False
        if self.campaign_ids and lead.campaign_id not in self.campaign_ids:
            return False
        if self.source_ids and lead.source_id not in self.source_ids:
            return False
        if self.medium_ids and lead.medium_id not in self.medium_ids:
            return False
        domain = literal_eval(self.domain or '[]')
        if domain and not lead.filtered_domain(domain):
            return False
        return self._match_extra(lead)

    def _match_extra(self, lead):
        """Hook for additional criteria in inheriting modules."""
        return True

    # ------------------------------------------------------------------
    # Salesperson selection
    # ------------------------------------------------------------------
    def _get_eligible_members(self, date=None):
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        members = self.team_id.crm_team_member_ids.filtered(lambda m: m._routing_available_on(date))
        if self.expertise_ids:
            members = members.filtered(lambda m: not (self.expertise_ids - m.routing_expertise_ids))
        if self.respect_capacity and members:
            open_counts = members._routing_open_lead_counts(members.user_id)
            members = members.filtered(lambda m: m._routing_has_capacity(open_counts))
        return members

    def _assign(self, lead):
        """Return (team, user, reason) for the lead according to this rule."""
        self.ensure_one()
        team, method, users = self.team_id, self.assign_method, self.env['res.users']
        if method == 'team_only':
            return team, users, self.env._('Rule "%s": team only', self.name)
        if method == 'leader':
            return team, team.user_id, self.env._('Rule "%s": team leader', self.name)

        user, reason = users, ''
        members = self._get_eligible_members()
        if members:
            picker = getattr(self, '_pick_%s' % method, None)
            if picker is None:
                _logger.warning('Assignment method "%s" is not implemented (_pick_%s)', method, method)
            else:
                user, reason = picker(lead, members)
        if user:
            return team, user, self.env._('Rule "%(rule)s": %(reason)s', rule=self.name, reason=reason)
        if self.fallback == 'leader':
            return team, team.user_id, self.env._(
                'Rule "%s": no eligible salesperson, assigned to the team leader', self.name)
        return team, users, self.env._('Rule "%s": no eligible salesperson', self.name)

    @staticmethod
    def _ratio(count, member):
        return count / float(max(member.routing_weight, 1))

    def _pick_round_robin(self, lead, members):
        """The member who has waited the longest for a lead of this rule."""
        last = self.env['crm.routing.log']._last_assignment(members.user_id, self)
        chosen = members.sorted(lambda m: (last.get(m.user_id.id) or 0, m.id))[0]
        return chosen.user_id, self.env._('round robin')

    def _pick_balanced(self, lead, members):
        """The member with the fewest assignments in the team (weighted)."""
        counts = self.env['crm.routing.log']._count_assignments(
            members.user_id, team=self.team_id,
            campaign=lead.campaign_id if self.balance_by_campaign else None,
            days=self.balance_window_days)
        chosen = members.sorted(lambda m: (self._ratio(counts.get(m.user_id.id, 0), m), m.id))[0]
        return chosen.user_id, self.env._('balanced (%s previous assignments)', counts.get(chosen.user_id.id, 0))

    def _pick_least_loaded(self, lead, members):
        """The member with the fewest open leads (weighted)."""
        counts = members._routing_open_lead_counts(members.user_id)
        chosen = members.sorted(lambda m: (self._ratio(counts.get(m.user_id.id, 0), m), m.id))[0]
        return chosen.user_id, self.env._('lowest workload (%s open)', counts.get(chosen.user_id.id, 0))

    @api.model
    def _previous_month_range(self, reference=None):
        reference = reference or fields.Date.context_today(self)
        first_current = reference.replace(day=1)
        return first_current - relativedelta(months=1), first_current - relativedelta(days=1)

    def _get_performance_scores(self, lead, members, date_from, date_to):
        """{user_id: score}. Default: expected revenue won in the team during the period.
        Override to use another metric."""
        groups = self.env['crm.lead'].sudo()._read_group([
            ('team_id', '=', self.team_id.id),
            ('user_id', 'in', members.user_id.ids),
            ('won_status', '=', 'won'),
            ('date_closed', '>=', datetime.combine(date_from, time.min)),
            ('date_closed', '<=', datetime.combine(date_to, time.max)),
        ], ['user_id'], ['expected_revenue:sum'])
        return {user.id: amount or 0.0 for user, amount in groups}

    def _pick_top_performer(self, lead, members):
        date_from, date_to = self._previous_month_range()
        scores = self._get_performance_scores(lead, members, date_from, date_to)
        chosen = members.sorted(lambda m: (-scores.get(m.user_id.id, 0.0), m.id))[0]
        return chosen.user_id, self.env._(
            'top performer %(start)s - %(end)s (%(score).2f)',
            start=date_from, end=date_to, score=scores.get(chosen.user_id.id, 0.0))

    def _top_invoiced_domain(self, members, date_from, date_to):
        """Invoices counted by "Top seller by invoicing". Override to filter by
        document type, journal, etc."""
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('invoice_user_id', 'in', members.user_id.ids),
        ]
        if 'team_id' in self.env['account.move']._fields:  # added by the Sales module
            domain.append(('team_id', '=', self.team_id.id))
        return domain

    def _pick_top_invoiced(self, lead, members):
        """Salesperson with the highest untaxed invoicing in the team last month.
        Without the Invoicing module it behaves like "Top performer"."""
        if 'account.move' not in self.env:
            return self._pick_top_performer(lead, members)
        date_from, date_to = self._previous_month_range()
        groups = self.env['account.move'].sudo()._read_group(
            self._top_invoiced_domain(members, date_from, date_to),
            ['invoice_user_id'], ['amount_untaxed_signed:sum'])
        scores = {user.id: amount or 0.0 for user, amount in groups}
        chosen = members.sorted(lambda m: (-scores.get(m.user_id.id, 0.0), m.id))[0]
        return chosen.user_id, self.env._(
            'top invoicing %(start)s - %(end)s (%(score).2f)',
            start=date_from, end=date_to, score=scores.get(chosen.user_id.id, 0.0))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('crm_lead_routing.action_crm_routing_log')
        action['domain'] = [('rule_id', '=', self.id)]
        return action
