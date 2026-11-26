# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

LEAD_FIELDS = 'created_time,field_data,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,is_organic'


class CrmFacebookForm(models.Model):
    _name = 'crm.facebook.form'
    _description = 'Facebook Lead Ads Form'
    _order = 'page_id, name'

    name = fields.Char('Form', required=True)
    facebook_form_id = fields.Char('Form ID', required=True, index=True)
    page_id = fields.Many2one('crm.facebook.page', 'Page', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)
    get_leads = fields.Boolean('Fetch Leads', help='Include this form in the scheduled download.')
    field_ids = fields.One2many('crm.facebook.form.field', 'form_id', 'Field Mapping')
    last_fetch = fields.Datetime('Last Fetch', readonly=True, copy=False)
    lead_count = fields.Integer('Lead Count', compute='_compute_lead_count')

    # Marketing
    campaign_id = fields.Many2one('utm.campaign', 'Campaign',
                                  help='If empty, the Facebook campaign of the ad is used.')
    source_id = fields.Many2one('utm.source', 'Source')
    medium_id = fields.Many2one('utm.medium', 'Medium',
                                help='If empty, the Facebook ad is used as medium.')

    # Enrutamiento
    routing_rule_id = fields.Many2one(
        'crm.routing.rule', 'Forced Rule',
        help='Always apply this rule to the leads of this form. If empty, all rules are evaluated by priority.')
    team_id = fields.Many2one(
        'crm.team', 'Fallback Team',
        domain="['|', ('use_leads', '=', True), ('use_opportunities', '=', True)]",
        help='If no rule matches, the lead is assigned to this team and its leader.')

    _form_unique = models.Constraint('unique(page_id, facebook_form_id)', 'This form is already registered.')

    def _compute_lead_count(self):
        groups = self.env['crm.lead'].with_context(active_test=False)._read_group(
            [('facebook_form_id', 'in', self.ids)], ['facebook_form_id'], ['__count'])
        counts = {form.id: count for form, count in groups}
        for form in self:
            form.lead_count = counts.get(form.id, 0)

    def _access_token(self):
        return self.page_id.sudo().access_token

    def action_get_fields(self):
        """Read the form questions and propose the default mapping."""
        Graph = self.env['crm.facebook.graph']
        Field = self.env['crm.facebook.form.field']
        for form in self:
            result = Graph._get(form.facebook_form_id, {'access_token': form._access_token(), 'fields': 'questions'})
            form.field_ids.unlink()
            for question in result.get('questions', []):
                Field.create({
                    'form_id': form.id,
                    'name': question.get('label') or question['key'],
                    'facebook_field': question['key'],
                })
            form.field_ids.action_guess_mapping()
        return True

    def action_guess_mapping(self):
        self.field_ids.action_guess_mapping()
        return True

    def action_fetch_leads(self):
        for form in self:
            form._fetch_leads()
        return True

    def action_view_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'crm.lead',
            'view_mode': 'list,kanban,form',
            'domain': [('facebook_form_id', '=', self.id)],
            'context': {'active_test': False, 'create': False},
        }

    def _fetch_leads(self, auto_commit=False):
        """Download the recent leads of the form and create the missing ones."""
        self.ensure_one()
        Graph = self.env['crm.facebook.graph']
        Lead = self.env['crm.lead']
        lookback = int(Graph._get_param('crm_fb_lookback_days', 10) or 10)
        since = fields.Datetime.now() - timedelta(days=lookback)
        params = {
            'access_token': self._access_token(),
            'fields': LEAD_FIELDS,
            'filtering': '[{"field":"time_created","operator":"GREATER_THAN","value":%d}]'
                         % int(since.timestamp()),
            'limit': 100,
        }
        created = Lead.browse()
        for data in Graph._iterate('%s/leads' % self.facebook_form_id, params, raise_error=not auto_commit):
            if Lead.with_context(active_test=False).search_count([('facebook_lead_id', '=', data.get('id'))],
                                                                 limit=1):
                continue
            try:
                with self.env.cr.savepoint():
                    created |= Lead._facebook_create_lead(data, self)
            except Exception:
                _logger.exception('Could not create Facebook lead %s (form %s)',
                                  data.get('id'), self.name)
            if auto_commit:
                self.env.cr.commit()
        self.last_fetch = fields.Datetime.now()
        _logger.info('Facebook form "%s": %s new leads', self.name, len(created))
        return created

    @api.model
    def _cron_fetch_leads(self):
        for form in self.search([('get_leads', '=', True)]):
            try:
                form._fetch_leads(auto_commit=True)
                self.env.cr.commit()
            except Exception:
                self.env.cr.rollback()
                _logger.exception('Error fetching leads of Facebook form %s', form.name)
