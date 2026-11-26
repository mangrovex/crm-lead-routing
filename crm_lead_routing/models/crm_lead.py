# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

AUTO_CREATE_PARAM = 'crm_lead_routing.auto_create'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    routing_channel = fields.Selection(
        selection='_selection_routing_channel', string='Inbound Channel', index=True, tracking=True,
        help='Channel the lead came from; used by the routing rules.')
    industry_id = fields.Many2one(
        'res.partner.industry', 'Industry', compute='_compute_industry_id', store=True, readonly=False,
        tracking=True)
    routing_rule_id = fields.Many2one('crm.routing.rule', 'Routing Rule', readonly=True, copy=False,
                                      index='btree_not_null', ondelete='set null')
    routing_date = fields.Datetime('Routing Date', readonly=True, copy=False)
    routing_log_ids = fields.One2many('crm.routing.log', 'lead_id', 'Routing History', readonly=True)

    @api.model
    def _selection_routing_channel(self):
        """Extend with super() to add channels (e.g. 'facebook')."""
        _ = self.env._
        labels = {
            'manual': _('Manual'),
            'email': _('Email'),
            'website': _('Website'),
            'phone': _('Phone'),
            'import': _('Import'),
            'api': _('Integration / API'),
        }
        return list(labels.items())

    @api.depends('partner_id')
    def _compute_industry_id(self):
        for lead in self:
            industry = lead.partner_id.industry_id or lead.partner_id.commercial_partner_id.industry_id
            if industry:
                lead.industry_id = industry

    # ------------------------------------------------------------------
    # Automatic routing on creation
    # ------------------------------------------------------------------
    @api.model
    def _routing_auto_create_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(AUTO_CREATE_PARAM) in ('1', 'True', 'true')

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        ctx = self.env.context
        if ctx.get('crm_routing_skip'):
            return leads
        forced = ctx.get('crm_routing_auto')
        auto_enabled = forced is None and self._routing_auto_create_enabled()
        rule = self.env['crm.routing.rule'].browse(ctx.get('crm_routing_rule_id') or []).exists()
        to_route = self.browse()
        for lead, vals in zip(leads, vals_list):
            if forced or (auto_enabled and not vals.get('user_id')):
                to_route |= lead
        if to_route:
            to_route._route(trigger=ctx.get('crm_routing_trigger') or 'create', rule=rule or None)
        return leads

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------
    def _route(self, trigger='manual', rule=None):
        """Route each lead: find the rule (or use ``rule``), pick team and
        salesperson, write the result and record it in the routing log.

        Return {lead_id: (team, user, reason)} for the applied assignments.
        """
        Rule = self.env['crm.routing.rule'].sudo()
        Log = self.env['crm.routing.log'].sudo()
        result = {}
        leads = self.with_context(crm_routing_auto=False, crm_routing_rule_id=False)
        for lead in leads:
            applied_rule = rule.sudo() if rule else Rule._find_rule(lead)
            if applied_rule:
                team, user, reason = applied_rule._assign(lead)
            else:
                outcome = lead._routing_fallback(trigger)
                if not outcome:
                    _logger.info('Lead %s: no routing rule matches', lead.id)
                    continue
                team, user, reason = outcome
            previous_user = lead.user_id
            vals = {
                'routing_rule_id': applied_rule.id or False,
                'routing_date': fields.Datetime.now(),
                'user_id': user.id or False,
            }
            if team:
                vals['team_id'] = team.id
            lead.write(vals)
            Log.create({
                'lead_id': lead.id,
                'rule_id': applied_rule.id or False,
                'team_id': (team or lead.team_id).id or False,
                'user_id': user.id or False,
                'previous_user_id': previous_user.id or False,
                'campaign_id': lead.campaign_id.id or False,
                'channel': lead.routing_channel or False,
                'trigger': trigger,
                'reason': reason,
                'company_id': (lead.company_id or self.env.company).id,
            })
            result[lead.id] = (team, user, reason)
        return result

    def _routing_fallback(self, trigger):
        """What to do when no rule matches.

        Return ``(team, user, reason)`` to apply an assignment, or ``None`` to
        leave the lead untouched. Hook for inheriting modules.
        """
        self.ensure_one()
        return None

    def action_route(self):
        """Button / mass action: (re)route the selected leads."""
        results = self._route(trigger='manual')
        skipped = len(self) - len(results)
        message = self.env._('%s lead(s) routed.', len(results))
        if skipped:
            message += ' ' + self.env._('%s without a matching rule.', skipped)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if results else 'warning',
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'} if len(self) > 1 else
                        {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
