# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestCrmLeadRouting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_create_nolog=True))
        group_salesman = cls.env.ref('sales_team.group_sale_salesman')
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login):
            return Users.create({'name': login.title(), 'login': login, 'email': '%s@example.com' % login,
                                 'group_ids': [(6, 0, [group_salesman.id])]})

        cls.leader = user('leader')
        cls.ana, cls.beto, cls.carla = user('ana'), user('beto'), user('carla')
        cls.team_costa = cls.env['crm.team'].create({'name': 'Costa', 'user_id': cls.leader.id, 'use_leads': True})
        cls.team_sierra = cls.env['crm.team'].create({'name': 'Sierra', 'user_id': cls.leader.id})
        Member = cls.env['crm.team.member']
        cls.m_ana = Member.create({'crm_team_id': cls.team_costa.id, 'user_id': cls.ana.id, 'assignment_max': 0})
        cls.m_beto = Member.create({'crm_team_id': cls.team_costa.id, 'user_id': cls.beto.id, 'assignment_max': 0})
        cls.m_carla = Member.create({'crm_team_id': cls.team_sierra.id, 'user_id': cls.carla.id,
                                     'assignment_max': 0})
        cls.corporate = cls.env['crm.routing.expertise'].create({'name': 'Test corporativo'})
        cls.industry = cls.env['res.partner.industry'].create({'name': 'Test salud'})
        Rule = cls.env['crm.routing.rule']
        cls.env['crm.routing.rule'].search([]).active = False
        cls.rule_corp = Rule.create({
            'name': 'Costa corporativo', 'sequence': 1, 'team_id': cls.team_costa.id,
            'industry_ids': [(6, 0, cls.industry.ids)], 'expertise_ids': [(6, 0, cls.corporate.ids)],
            'assign_method': 'balanced',
        })
        cls.rule_costa = Rule.create({
            'name': 'Costa', 'sequence': 5, 'team_id': cls.team_costa.id,
            'city_names': 'Guayaquil, Samborondón', 'assign_method': 'balanced',
        })
        cls.rule_sierra = Rule.create({
            'name': 'Sierra', 'sequence': 10, 'team_id': cls.team_sierra.id,
            'city_names': 'Quito', 'assign_method': 'least_loaded',
        })

    def _lead(self, **vals):
        vals.setdefault('name', 'Lead')
        vals.setdefault('type', 'lead')
        return self.env['crm.lead'].with_context(crm_routing_skip=True).create(vals)

    def test_region_match_accent_insensitive(self):
        lead = self._lead(city='  SAMBORONDON ')
        lead.action_route()
        self.assertEqual(lead.team_id, self.team_costa)
        self.assertIn(lead.user_id, self.ana | self.beto)
        self.assertEqual(lead.routing_rule_id, self.rule_costa)
        self.assertEqual(len(lead.routing_log_ids), 1)

    def test_region_other_team(self):
        lead = self._lead(city='Quito')
        lead.action_route()
        self.assertEqual((lead.team_id, lead.user_id), (self.team_sierra, self.carla))

    def test_no_rule_keeps_lead(self):
        lead = self._lead(city='Lima', user_id=self.leader.id)
        lead.action_route()
        self.assertEqual(lead.user_id, self.leader)
        self.assertFalse(lead.routing_log_ids)

    def test_balanced_alternates(self):
        users = self.env['res.users']
        for _i in range(4):
            lead = self._lead(city='Guayaquil')
            lead._route()
            users |= lead.user_id
        self.assertEqual(users, self.ana | self.beto)
        counts = self.env['crm.routing.log']._count_assignments(self.ana | self.beto, team=self.team_costa)
        self.assertEqual(counts, {self.ana.id: 2, self.beto.id: 2})

    def test_weight(self):
        self.m_ana.routing_weight = 3
        for _i in range(4):
            self._lead(city='Guayaquil')._route()
        counts = self.env['crm.routing.log']._count_assignments(self.ana | self.beto, team=self.team_costa)
        self.assertEqual(counts, {self.ana.id: 3, self.beto.id: 1})

    def test_expertise_and_industry(self):
        self.m_beto.routing_expertise_ids = self.corporate
        partner = self.env['res.partner'].create({'name': 'Clínica', 'is_company': True,
                                                  'industry_id': self.industry.id})
        lead = self._lead(partner_id=partner.id, city='Guayaquil')
        self.assertEqual(lead.industry_id, self.industry)
        lead._route()
        self.assertEqual(lead.routing_rule_id, self.rule_corp)
        self.assertEqual(lead.user_id, self.beto)

    def test_expertise_nobody_falls_back_to_leader(self):
        lead = self._lead(industry_id=self.industry.id)
        lead._route()
        self.assertEqual(lead.routing_rule_id, self.rule_corp)
        self.assertEqual(lead.user_id, self.leader)
        self.rule_corp.fallback = 'unassigned'
        lead._route()
        self.assertFalse(lead.user_id)
        self.assertEqual(lead.team_id, self.team_costa)

    def test_availability(self):
        self.m_ana.assignment_optout = True
        today = fields.Date.context_today(self.m_beto)
        self.m_beto.write({'routing_unavailable_from': today - timedelta(days=1),
                           'routing_unavailable_until': today + timedelta(days=1)})
        self.assertFalse(self.m_beto.routing_is_available)
        lead = self._lead(city='Guayaquil')
        lead._route()
        self.assertEqual(lead.user_id, self.leader)
        self.m_beto.routing_unavailable_until = today - timedelta(days=1)
        lead._route()
        self.assertEqual(lead.user_id, self.beto)

    def test_capacity_open_leads(self):
        self.rule_costa.assign_method = 'least_loaded'
        self.m_ana.routing_max_open_leads = 1
        self.m_beto.routing_max_open_leads = 1
        self._lead(user_id=self.ana.id, team_id=self.team_costa.id)
        lead = self._lead(city='Guayaquil')
        lead._route()
        self.assertEqual(lead.user_id, self.beto)
        other = self._lead(city='Guayaquil')
        other._route()
        self.assertEqual(other.user_id, self.leader, 'Both full: team leader')
        self.rule_costa.respect_capacity = False
        other._route()
        self.assertIn(other.user_id, self.ana | self.beto)

    def test_round_robin(self):
        self.rule_costa.assign_method = 'round_robin'
        sequence = []
        for _i in range(4):
            lead = self._lead(city='Guayaquil')
            lead._route()
            sequence.append(lead.user_id)
        self.assertNotEqual(sequence[0], sequence[1])
        self.assertEqual(sequence[0], sequence[2])

    def test_top_performer(self):
        self.rule_costa.assign_method = 'top_performer'
        date_from, _date_to = self.rule_costa._previous_month_range()
        won_stage = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        won = self._lead(type='opportunity', user_id=self.beto.id, team_id=self.team_costa.id,
                         expected_revenue=1000, stage_id=won_stage.id)
        won.date_closed = fields.Datetime.to_datetime(date_from) + timedelta(days=2)
        self.assertEqual(won.won_status, 'won')
        lead = self._lead(city='Guayaquil')
        lead._route()
        self.assertEqual(lead.user_id, self.beto)

    def test_channel_and_domain(self):
        self.rule_costa.write({'channel': 'website', 'domain': "[('expected_revenue', '>', 100)]"})
        lead = self._lead(city='Guayaquil', routing_channel='email', expected_revenue=500)
        self.assertFalse(self.env['crm.routing.rule']._find_rule(lead))
        lead.routing_channel = 'website'
        self.assertEqual(self.env['crm.routing.rule']._find_rule(lead), self.rule_costa)
        lead.expected_revenue = 50
        self.assertFalse(self.env['crm.routing.rule']._find_rule(lead))

    def test_auto_create(self):
        Lead = self.env['crm.lead']
        lead = Lead.create({'name': 'Sin auto', 'city': 'Quito', 'user_id': False})
        self.assertFalse(lead.routing_rule_id)
        self.env['ir.config_parameter'].sudo().set_param('crm_lead_routing.auto_create', 'True')
        lead = Lead.create({'name': 'Auto', 'city': 'Quito', 'user_id': False})
        self.assertEqual(lead.user_id, self.carla)
        lead = Lead.create({'name': 'Con vendedor', 'city': 'Quito', 'user_id': self.leader.id})
        self.assertEqual(lead.user_id, self.leader, 'Leads created with a salesperson are not routed')
        lead = Lead.with_context(crm_routing_auto=True, crm_routing_rule_id=self.rule_costa.id).create(
            {'name': 'Forzada', 'city': 'Quito'})
        self.assertEqual(lead.routing_rule_id, self.rule_costa)

    def test_action_notification(self):
        leads = self._lead(city='Quito') | self._lead(city='Lima')
        action = leads.action_route()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(leads[0].user_id, self.carla)

    def test_top_invoiced(self):
        if 'account.move' not in self.env:
            self.skipTest('Invoicing is not installed')
        self.rule_costa.assign_method = 'top_invoiced'
        date_from, _date_to = self.rule_costa._previous_month_range()
        partner = self.env['res.partner'].create({'name': 'Cliente'})
        product = self.env['product.product'].create({'name': 'Servicio', 'list_price': 100})
        vals = {
            'move_type': 'out_invoice', 'partner_id': partner.id, 'invoice_date': date_from,
            'invoice_user_id': self.ana.id,
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 3, 'price_unit': 100})],
        }
        if 'team_id' in self.env['account.move']._fields:
            vals['team_id'] = self.team_costa.id
        invoice = self.env['account.move'].create(vals)
        invoice.action_post()
        lead = self._lead(city='Guayaquil')
        lead._route()
        self.assertEqual(lead.user_id, self.ana)
