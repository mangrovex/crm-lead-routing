# -*- coding: utf-8 -*-
import logging

from dateutil import parser as date_parser
from dateutil import tz

from odoo import api, fields, models
from odoo.tools import plaintext2html

_logger = logging.getLogger(__name__)


def facebook_datetime(value):
    """'2026-11-25T14:03:11+0000' -> datetime naive UTC datetime (Odoo format)."""
    if not value:
        return False
    parsed = date_parser.isoparse(value) if 'T' in value else date_parser.parse(value)
    if parsed.tzinfo:
        parsed = parsed.astimezone(tz.UTC).replace(tzinfo=None)
    return parsed


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    facebook_lead_id = fields.Char('Facebook Lead ID', readonly=True, copy=False, index='btree_not_null')
    facebook_form_id = fields.Many2one('crm.facebook.form', 'Facebook Form', readonly=True,
                                       index='btree_not_null', ondelete='set null')
    facebook_page_id = fields.Many2one('crm.facebook.page', 'Facebook Page',
                                       related='facebook_form_id.page_id', store=True)
    facebook_adset_id = fields.Many2one('crm.facebook.adset', 'Ad Set', readonly=True,
                                        ondelete='set null')
    facebook_ad_id = fields.Many2one('utm.medium', 'Facebook Ad', readonly=True, ondelete='set null')
    facebook_campaign_id = fields.Many2one('utm.campaign', 'Facebook Campaign', readonly=True,
                                           ondelete='set null')
    facebook_date_create = fields.Datetime('Facebook Date', readonly=True)
    facebook_is_organic = fields.Boolean('Organic', readonly=True)

    _facebook_lead_unique = models.Constraint('unique(facebook_lead_id)', 'This Facebook lead already exists.')

    @api.model
    def _selection_routing_channel(self):
        return super()._selection_routing_channel() + [('facebook', 'Facebook Lead Ads')]

    # ------------------------------------------------------------------
    # Creation from Facebook
    # ------------------------------------------------------------------
    @api.model
    def _facebook_flatten(self, data):
        """Flatten ``field_data`` ([{name, values}]) into plain dictionary keys."""
        flat = {k: v for k, v in data.items() if k != 'field_data'}
        for item in data.get('field_data') or []:
            if item.get('name') and item.get('values'):
                flat[item['name']] = item['values'][0]
        return flat

    @api.model
    def _facebook_convert_value(self, odoo_field, value):
        ttype = odoo_field.ttype
        if value in (None, ''):
            return False
        if ttype == 'many2one':
            return self._facebook_find_record(odoo_field.relation, value).id or False
        if ttype in ('float', 'monetary'):
            return float(str(value).replace(',', '.'))
        if ttype == 'integer':
            return int(float(value))
        if ttype == 'boolean':
            return str(value).lower() in ('1', 'true', 'yes', 'si', 'sí')
        if ttype == 'datetime':
            return facebook_datetime(value)
        if ttype == 'date':
            parsed = facebook_datetime(value)
            return parsed and parsed.date()
        if ttype == 'selection':
            keys = [key for key, _label in self.env[odoo_field.model]._fields[odoo_field.name]
                    ._description_selection(self.env)]
            return value if value in keys else False
        return value

    @api.model
    def _facebook_find_record(self, model, value, extra_domain=None):
        """Find a record by name or, when the model has one, by code (country 'US', state 'CA')."""
        Comodel = self.env[model]
        domain = list(extra_domain or [])
        value = str(value).strip()
        record = Comodel.search(domain + [('display_name', '=ilike', value)], limit=1)
        if not record and 'code' in Comodel._fields:
            record = Comodel.search(domain + [('code', '=ilike', value)], limit=1)
        return record

    @api.model
    def _facebook_values_from_fields(self, flat, form):
        """Return (vals, notes). Unmapped answers are kept in the notes."""
        vals, notes, unmapped = {}, [], []
        mappings = {m.facebook_field: m.odoo_field for m in form.field_ids if m.odoo_field}
        technical = {
            'id', 'created_time', 'ad_id', 'ad_name', 'adset_id', 'adset_name', 'campaign_id', 'campaign_name',
            'is_organic', 'form_id'}
        for key, value in flat.items():
            odoo_field = mappings.get(key)
            if not odoo_field:
                if key not in technical:
                    unmapped.append('%s: %s' % (key, value))
                continue
            notes.append('%s: %s' % (odoo_field.field_description, value))
            try:
                vals[odoo_field.name] = self._facebook_convert_value(odoo_field, value)
            except (ValueError, TypeError):
                _logger.warning('Invalid value "%s" for %s; kept in the notes only', value, odoo_field.name)
        return vals, notes + unmapped

    @api.model
    def _facebook_prepare_values(self, data, form):
        flat = self._facebook_flatten(data)
        vals, notes = self._facebook_values_from_fields(flat, form)
        campaign = form.campaign_id or self.env['utm.campaign']._facebook_get_or_create(
            flat.get('campaign_id'), flat.get('campaign_name'))
        ad = self.env['utm.medium']._facebook_get_or_create(flat.get('ad_id'), flat.get('ad_name'))
        if not vals.get('city') and flat.get('city'):
            vals['city'] = flat['city']
        if not vals.get('country_id') and flat.get('country'):
            vals['country_id'] = self._facebook_find_record('res.country', flat['country']).id or False
        if not vals.get('state_id') and flat.get('state'):
            country_domain = [('country_id', '=', vals['country_id'])] if vals.get('country_id') else []
            vals['state_id'] = self._facebook_find_record(
                'res.country.state', flat['state'], country_domain).id or False
        vals.update({
            'name': vals.get('name') or '%s - %s' % (form.name, flat.get('id')),
            'description': plaintext2html('\n'.join(notes)),
            'facebook_lead_id': flat.get('id'),
            'facebook_form_id': form.id,
            'facebook_is_organic': bool(flat.get('is_organic')),
            'facebook_date_create': facebook_datetime(flat.get('created_time')),
            'facebook_adset_id': self.env['crm.facebook.adset']._facebook_get_or_create(
                flat.get('adset_id'), flat.get('adset_name')).id,
            'facebook_ad_id': ad.id,
            'facebook_campaign_id': campaign.id,
            'campaign_id': campaign.id,
            'source_id': form.source_id.id,
            'medium_id': (form.medium_id or ad).id,
            'routing_channel': 'facebook',
            'user_id': False,
        })
        if form.team_id:
            vals['team_id'] = form.team_id.id
        return vals

    @api.model
    def _facebook_create_lead(self, data, form):
        """Create the lead and hand it over to the routing engine."""
        vals = self._facebook_prepare_values(data, form)
        return self.with_context(
            crm_routing_auto=True,
            crm_routing_rule_id=form.routing_rule_id.id,
            crm_routing_trigger='create',
            mail_create_nosubscribe=True,
        ).create(vals)

    def _routing_fallback(self, trigger):
        """No matching rule: use the fallback team of the form and its leader."""
        team = self.facebook_form_id.team_id
        if team:
            return team, team.user_id, self.env._(
                'Form "%s": fallback team, team leader', self.facebook_form_id.name)
        return super()._routing_fallback(trigger)

    @api.model
    def _cron_fetch_facebook_leads(self):
        self.env['crm.facebook.form']._cron_fetch_leads()
