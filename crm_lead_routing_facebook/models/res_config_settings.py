# -*- coding: utf-8 -*-
from urllib.parse import urlencode

from odoo import fields, models

from .graph_api import DEFAULT_GRAPH_URL

OAUTH_SCOPES = 'leads_retrieval,pages_show_list,pages_manage_ads,pages_read_engagement,ads_management'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crm_fb_app_id = fields.Char('App ID', config_parameter='crm_lead_routing_facebook.crm_fb_app_id')
    crm_fb_app_secret = fields.Char('App Secret', config_parameter='crm_lead_routing_facebook.crm_fb_app_secret')
    crm_fb_access_token = fields.Char('Access Token', config_parameter='crm_lead_routing_facebook.crm_fb_access_token')
    crm_fb_api_url_host = fields.Char('Graph API URL', config_parameter='crm_lead_routing_facebook.crm_fb_api_url_host',
                                      default=DEFAULT_GRAPH_URL)
    crm_fb_lookback_days = fields.Integer('Lookback Days', config_parameter='crm_lead_routing_facebook.crm_fb_lookback_days',
                                          default=10,
                                          help='Maximum age of the leads that are downloaded.')

    def action_crm_fb_get_access_token(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        query = urlencode({
            'response_type': 'token',
            'client_id': self.crm_fb_app_id,
            'redirect_uri': '%s/crm_lead_routing_facebook/auth' % base_url,
            'scope': OAUTH_SCOPES,
        })
        return {'type': 'ir.actions.act_url', 'url': 'https://www.facebook.com/dialog/oauth?' + query,
                'target': 'self'}

    def action_crm_fb_get_pages(self):
        """Import / update the pages managed by the user token."""
        self.ensure_one()
        Page = self.env['crm.facebook.page'].with_context(active_test=False)
        token = self.env['ir.config_parameter'].sudo().get_param('crm_lead_routing_facebook.crm_fb_access_token')
        for item in self.env['crm.facebook.graph']._iterate('me/accounts', {'access_token': token}):
            page = Page.search([('name', '=', item.get('id'))], limit=1)
            vals = {'label': item.get('name'), 'access_token': item.get('access_token')}
            if page:
                page.sudo().write(vals)
            else:
                Page.sudo().create(dict(vals, name=item.get('id')))
        return self.env['ir.actions.act_window']._for_xml_id('crm_lead_routing_facebook.action_crm_facebook_page')
