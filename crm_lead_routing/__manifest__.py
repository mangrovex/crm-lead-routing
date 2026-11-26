# -*- coding: utf-8 -*-
{
    'name': 'Smart Lead Routing',
    'summary': 'Route CRM leads by region, industry, expertise, workload and availability',
    'description': """
Rule-based lead routing engine for Odoo CRM.

* Prioritized routing rules (first match wins) filtering by inbound channel,
  region (country, state, city), industry, tags, UTM and an advanced domain.
* Builds on native sales team members (crm.team.member) and adds expertise,
  weight, absences and a maximum of open leads.
* Assignment methods: team leader, round robin, balanced, lowest workload,
  top performer and top seller by invoicing.
* Routing log, "Route" button and mass action, optional routing on creation.
* Hooks for other modules to add channels, criteria and methods.
""",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'author': 'mangrovex',
    'maintainer': 'mangrovex',
    'website': 'https://mangrovex.github.io/',
    'license': 'LGPL-3',
    'depends': ['crm'],
    'data': [
        'security/ir.model.access.csv',
        'security/crm_routing_security.xml',
        'data/crm_routing_data.xml',
        'views/crm_routing_expertise_views.xml',
        'views/crm_team_member_views.xml',
        'views/crm_routing_log_views.xml',
        'views/crm_routing_rule_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_team_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
