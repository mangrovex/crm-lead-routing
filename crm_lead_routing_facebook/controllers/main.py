# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

FRAGMENT_TO_QUERY = """<html><head><script>
    var l = window.location, q = l.hash.substring(1);
    window.location = q ? l.pathname + '?' + q : '/odoo';
</script></head><body></body></html>"""


class CrmFacebookOAuth(http.Controller):

    @http.route('/crm_lead_routing_facebook/auth', type='http', auth='user')
    def crm_facebook_auth(self, **kw):
        """Facebook returns the token in the URL fragment (#access_token=...): it is first moved to
        the query string and then exchanged for a long-lived token."""
        kw.pop('debug', None)
        if not kw:
            return FRAGMENT_TO_QUERY
        if not request.env.user.has_group('base.group_system'):
            return request.redirect('/odoo')
        if kw.get('access_token'):
            ICP = request.env['ir.config_parameter'].sudo()
            result = request.env['crm.facebook.graph']._get('oauth/access_token', {
                'grant_type': 'fb_exchange_token',
                'client_id': ICP.get_param('crm_lead_routing_facebook.crm_fb_app_id'),
                'client_secret': ICP.get_param('crm_lead_routing_facebook.crm_fb_app_secret'),
                'fb_exchange_token': kw['access_token'],
            }, raise_error=False)
            if result and result.get('access_token'):
                ICP.set_param('crm_lead_routing_facebook.crm_fb_access_token', result['access_token'])
            else:
                _logger.warning('Could not obtain the long-lived Facebook token')
        return request.redirect('/odoo/action-crm.crm_config_settings_action')
