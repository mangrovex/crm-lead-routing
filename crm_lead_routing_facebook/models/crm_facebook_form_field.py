# -*- coding: utf-8 -*-
from odoo import fields, models

MAPPABLE_TTYPES = ('boolean', 'char', 'date', 'datetime', 'float', 'html', 'integer', 'monetary',
                   'many2one', 'selection', 'text')
LEAD_FIELD_DOMAIN = [('model', '=', 'crm.lead'), ('store', '=', True), ('ttype', 'in', MAPPABLE_TTYPES)]


class CrmFacebookFormField(models.Model):
    _name = 'crm.facebook.form.field'
    _description = 'Facebook Form Field'

    form_id = fields.Many2one('crm.facebook.form', 'Form', required=True, ondelete='cascade', index=True)
    name = fields.Char('Question')
    facebook_field = fields.Char('Facebook Field', required=True)
    odoo_field = fields.Many2one('ir.model.fields', 'Odoo Field', domain=LEAD_FIELD_DOMAIN, ondelete='cascade')

    _field_unique = models.Constraint('unique(form_id, facebook_field)',
                                      'This Facebook field is already mapped in this form.')

    def action_guess_mapping(self):
        Mapping = self.env['crm.facebook.form.mapping']
        for rec in self.filtered(lambda r: not r.odoo_field):
            mapping = Mapping.search([('facebook_field', '=', rec.facebook_field)], limit=1)
            if mapping:
                rec.odoo_field = mapping.odoo_field
        return True
