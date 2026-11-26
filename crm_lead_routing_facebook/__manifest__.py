# -*- coding: utf-8 -*-
{
    'name': 'Facebook Lead Ads Sync',
    'summary': 'Import Facebook Lead Ads leads into the CRM and route them automatically',
    'description': """
Downloads the leads of your Facebook Lead Ads forms, creates them in the CRM with
their campaign, ad set and ad, and hands them over to Smart Lead Routing
(crm_lead_routing).

* Pages, forms and Facebook-to-crm.lead field mapping.
* "Facebook Lead Ads" inbound channel and "Facebook Forms" criterion in routing rules.
* Forced rule or fallback team per form.

External service: this module calls the Meta Graph API (graph.facebook.com) with
the credentials you configure, only after you enter them in Settings.

Based on crm_facebook_leads by BADEP and Vauxoo (AGPL-3), rewritten for Odoo 19.
""",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'author': 'mangrovex',
    'maintainer': 'mangrovex',
    'website': 'https://mangrovex.github.io/',
    'license': 'AGPL-3',
    'depends': ['crm', 'utm', 'crm_lead_routing'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/crm.facebook.form.mapping.csv',
        'data/ir_cron.xml',
        'views/crm_facebook_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_routing_rule_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
