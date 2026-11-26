# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged, TransactionCase

GRAPH = 'odoo.addons.crm_lead_routing_facebook.models.graph_api.requests.get'


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def fb_lead(lead_id, city='Guayaquil', email='cliente@example.com'):
    return {
        'id': lead_id,
        'created_time': fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S+0000'),
        'ad_id': 'AD1', 'ad_name': 'Anuncio salud',
        'adset_id': 'AS1', 'adset_name': 'Conjunto Costa',
        'campaign_id': 'CMP1', 'campaign_name': 'Campaña noviembre',
        'is_organic': False,
        'field_data': [
            {'name': 'full_name', 'values': ['María Pérez']},
            {'name': 'email', 'values': [email]},
            {'name': 'city', 'values': [city]},
            {'name': 'plan_interes', 'values': ['Familiar']},
        ],
    }


@tagged('post_install', '-at_install')
class TestFacebookLeads(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        group = cls.env.ref('sales_team.group_sale_salesman')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.leader = Users.create({'name': 'Líder FB', 'login': 'fb_leader', 'group_ids': [(6, 0, group.ids)]})
        cls.seller = Users.create({'name': 'Vendedor FB', 'login': 'fb_seller', 'group_ids': [(6, 0, group.ids)]})
        cls.team = cls.env['crm.team'].create({'name': 'Facebook Costa', 'user_id': cls.leader.id})
        cls.env['crm.team.member'].create({'crm_team_id': cls.team.id, 'user_id': cls.seller.id,
                                           'assignment_max': 0})
        cls.page = cls.env['crm.facebook.page'].create({'name': '111', 'label': 'Mi página', 'access_token': 'x'})
        cls.form = cls.env['crm.facebook.form'].create({'name': 'Cotiza tu plan', 'facebook_form_id': '222',
                                                        'page_id': cls.page.id, 'get_leads': True})
        cls.env['crm.routing.rule'].search([]).active = False

    def _fetch(self, leads):
        with patch(GRAPH, return_value=FakeResponse({'data': leads})):
            return self.form._fetch_leads()

    def test_get_fields_and_mapping(self):
        payload = {'questions': [{'key': 'full_name', 'label': 'Nombre'}, {'key': 'email', 'label': 'Correo'},
                                 {'key': 'plan_interes', 'label': '¿Qué plan?'}]}
        with patch(GRAPH, return_value=FakeResponse(payload)):
            self.form.action_get_fields()
        mapped = {f.facebook_field: f.odoo_field.name for f in self.form.field_ids}
        self.assertEqual(mapped, {'full_name': 'contact_name', 'email': 'email_from', 'plan_interes': False})

    def _map_defaults(self):
        for key in ('full_name', 'email', 'city', 'plan_interes'):
            self.env['crm.facebook.form.field'].create({'form_id': self.form.id, 'facebook_field': key})
        self.form.action_guess_mapping()

    def test_fetch_routes_with_facebook_rule(self):
        self._map_defaults()
        rule = self.env['crm.routing.rule'].create({
            'name': 'Facebook Costa', 'channel': 'facebook', 'city_names': 'Guayaquil',
            'facebook_form_ids': [(6, 0, self.form.ids)], 'team_id': self.team.id,
            'assign_method': 'balanced'})
        leads = self._fetch([fb_lead('L1')])
        self.assertEqual(len(leads), 1)
        lead = leads
        self.assertEqual(lead.contact_name, 'María Pérez')
        self.assertEqual(lead.email_from, 'cliente@example.com')
        self.assertEqual(lead.city, 'Guayaquil')
        self.assertEqual(lead.routing_channel, 'facebook')
        self.assertEqual(lead.routing_rule_id, rule)
        self.assertEqual((lead.team_id, lead.user_id), (self.team, self.seller))
        self.assertEqual(lead.campaign_id.facebook_campaign_id, 'CMP1')
        self.assertEqual(lead.facebook_ad_id, lead.medium_id)
        self.assertEqual(lead.facebook_adset_id.facebook_adset_id, 'AS1')
        self.assertIn('plan_interes: Familiar', lead.description)
        # Second fetch: no duplicates, campaign and ad are reused
        again = self._fetch([fb_lead('L1'), fb_lead('L2')])
        self.assertEqual(len(again), 1)
        self.assertEqual(again.campaign_id, lead.campaign_id)

    def test_rule_limited_to_other_form(self):
        other = self.env['crm.facebook.form'].create({'name': 'Otro', 'facebook_form_id': '333',
                                                      'page_id': self.page.id})
        self.env['crm.routing.rule'].create({'name': 'Solo otro', 'facebook_form_ids': [(6, 0, other.ids)],
                                             'team_id': self.team.id})
        lead = self._fetch([fb_lead('L3')])
        self.assertFalse(lead.routing_rule_id)
        self.assertFalse(lead.user_id, 'Without rule nor fallback team the lead stays unassigned')

    def test_fallback_team(self):
        self.form.team_id = self.team
        lead = self._fetch([fb_lead('L4', city='Cuenca')])
        self.assertEqual((lead.team_id, lead.user_id), (self.team, self.leader))
        self.assertEqual(len(lead.routing_log_ids), 1)

    def test_forced_rule(self):
        rule = self.env['crm.routing.rule'].create({'name': 'Forzada', 'city_names': 'Quito',
                                                    'team_id': self.team.id, 'assign_method': 'leader'})
        self.form.routing_rule_id = rule
        lead = self._fetch([fb_lead('L5', city='Guayaquil')])
        self.assertEqual((lead.routing_rule_id, lead.user_id), (rule, self.leader))

    def test_api_error_does_not_crash_cron(self):
        with patch(GRAPH, return_value=FakeResponse({'error': {'code': 80005, 'message': 'rate limit'}})), \
                patch.object(type(self.env.cr), 'commit', lambda cr: None):
            result = self.form._fetch_leads(auto_commit=True)
        self.assertFalse(result)

    def test_pagination(self):
        pages = [FakeResponse({'data': [fb_lead('P1')], 'paging': {'next': 'https://graph.facebook.com/next'}}),
                 FakeResponse({'data': [fb_lead('P2')]})]
        with patch(GRAPH, side_effect=pages):
            leads = self.form._fetch_leads()
        self.assertEqual(sorted(leads.mapped('facebook_lead_id')), ['P1', 'P2'])

    def test_state_country_by_code(self):
        self._map_defaults()
        us = self.env.ref('base.us')
        california = self.env['res.country.state'].search([('country_id', '=', us.id), ('code', '=', 'CA')])
        rule = self.env['crm.routing.rule'].create({'name': 'California', 'state_ids': [(6, 0, california.ids)],
                                                    'team_id': self.team.id, 'assign_method': 'leader'})
        data = fb_lead('S1', city='San Diego')
        data['field_data'] += [{'name': 'state', 'values': ['CA']}, {'name': 'country', 'values': ['US']}]
        self.env['crm.facebook.form.field'].create({'form_id': self.form.id, 'facebook_field': 'country'})
        self.form.action_guess_mapping()
        lead = self._fetch([data])
        self.assertEqual((lead.country_id, lead.state_id), (us, california))
        self.assertEqual(lead.routing_rule_id, rule)
