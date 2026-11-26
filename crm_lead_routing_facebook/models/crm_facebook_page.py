# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmFacebookPage(models.Model):
    _name = 'crm.facebook.page'
    _description = 'Facebook Page'
    _order = 'label, name'

    label = fields.Char('Page Name')
    name = fields.Char('Page ID', required=True)
    access_token = fields.Char('Page Access Token', required=True, groups='base.group_system')
    form_ids = fields.One2many('crm.facebook.form', 'page_id', 'Forms')
    form_count = fields.Integer('Form Count', compute='_compute_form_count')
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint('unique(name)', 'This Facebook page is already registered.')

    @api.depends('label', 'name')
    def _compute_display_name(self):
        for page in self:
            page.display_name = page.label or page.name

    @api.depends('form_ids')
    def _compute_form_count(self):
        for page in self:
            page.form_count = len(page.form_ids)

    def action_get_forms(self):
        """Import the active forms of the page that do not exist yet."""
        Graph = self.env['crm.facebook.graph']
        Form = self.env['crm.facebook.form']
        for page in self:
            token = page.sudo().access_token
            existing = set(page.with_context(active_test=False).form_ids.mapped('facebook_form_id'))
            for form in Graph._iterate('%s/leadgen_forms' % page.name, {'access_token': token}):
                if form.get('id') in existing or form.get('status') != 'ACTIVE':
                    continue
                Form.create({'name': form.get('name') or form['id'], 'facebook_form_id': form['id'],
                             'page_id': page.id}).action_get_fields()
        return True
