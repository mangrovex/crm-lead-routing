# -*- coding: utf-8 -*-
import logging

import requests

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_GRAPH_URL = 'https://graph.facebook.com/v26.0'
PARAM_PREFIX = 'crm_lead_routing_facebook.'
TIMEOUT = 30


class CrmFacebookGraph(models.AbstractModel):
    """Minimal Meta Graph API client shared by pages, forms and settings."""
    _name = 'crm.facebook.graph'
    _description = 'Facebook Graph API Client'

    @api.model
    def _get_param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _base_url(self):
        return (self._get_param('crm_fb_api_url_host') or DEFAULT_GRAPH_URL).rstrip('/')

    @api.model
    def _get(self, path_or_url, params=None, raise_error=True):
        """GET on the Graph API. ``path_or_url`` is a path ('/me/accounts') or the full
        ``paging.next`` URL. Return the JSON, or None on failure when ``raise_error`` is False."""
        url = path_or_url if path_or_url.startswith('http') else self._base_url() + '/' + path_or_url.lstrip('/')
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            result = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            _logger.warning('Error calling the Facebook Graph API (%s): %s', url.split('?')[0], exc)
            if raise_error:
                raise UserError(self.env._('Could not reach Facebook: %s', exc))
            return None
        error = result.get('error')
        if error:
            _logger.warning('Facebook Graph API returned an error [code=%s]: %s', error.get('code'), error.get('message'))
            if raise_error:
                raise UserError(error.get('message') or self.env._('Unknown Facebook error'))
            return None
        return result

    @api.model
    def _iterate(self, path, params=None, raise_error=True):
        """Iterate over every page of a listing (``data`` + ``paging.next``)."""
        result = self._get(path, params=params, raise_error=raise_error)
        while result:
            yield from result.get('data', [])
            next_url = result.get('paging', {}).get('next')
            result = self._get(next_url, raise_error=raise_error) if next_url else None
