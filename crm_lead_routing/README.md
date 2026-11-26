# Smart Lead Routing (`crm_lead_routing`) — Odoo 19

Rule-based routing engine that sends each CRM lead to the right team and salesperson.

## How it works

1. A lead arrives (automatic routing on creation, **Route** button, or **Route** mass action).
2. Routing rules are evaluated by priority; the first matching rule wins.
3. The rule picks the **target team** and, among its eligible members, the **salesperson**.
4. The result is written on the lead and recorded in the **routing log**.

### Rule criteria (empty = any)

| Group | Criteria |
|---|---|
| Channel | Inbound channel (`manual`, `email`, `website`, `phone`, `import`, `api` + channels added by other modules), lead type |
| Region | Countries, states, cities (text, case and accent insensitive) |
| Industry / profile | Industry (of the lead or its partner), tags |
| Marketing | Campaign, source, medium |
| Advanced | Free domain on `crm.lead` |

### Eligible salespeople

Native sales team members (`crm.team.member`) are extended with:

- **Expertise** (`crm.routing.expertise`): rules can require one or more areas.
- **Weight**: share of leads with the *Balanced* and *Lowest workload* methods.
- **Unavailable from / until** (holidays, leave) plus the native **Pause assignment**.
- **Capacity**: native 30-day capacity (`assignment_max`) and a maximum of open leads.

### Assignment methods

| Method | Picks |
|---|---|
| Team leader | `team.user_id` |
| Round robin | the member who has waited the longest for a lead of this rule |
| Balanced | the member with the fewest assignments in the team (time window, optionally per campaign) |
| Lowest workload | the member with the fewest open leads |
| Top performer | highest expected revenue won last month |
| Top seller by invoicing | highest untaxed invoicing last month (requires Invoicing) |
| Team only | sets the team and leaves the salesperson empty (combine with Odoo's native assignment) |

When nobody is eligible the rule assigns the team leader or leaves the lead without salesperson.

## Configuration

- *CRM ▸ Configuration ▸ Lead Routing*: rules, salespeople and availability, expertise areas, assignment log.
- *Settings ▸ CRM ▸ Smart Lead Routing*: **Route leads on creation** (leads created without salesperson).

## Extending

```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _selection_routing_channel(self):                 # new channel
        return super()._selection_routing_channel() + [('whatsapp', 'WhatsApp')]

    def _routing_fallback(self, trigger):                 # no matching rule
        return super()._routing_fallback(trigger)

class CrmRoutingRule(models.Model):
    _inherit = 'crm.routing.rule'

    def _match_extra(self, lead):                         # extra criterion
        return super()._match_extra(lead)

    def _selection_assign_method(self):                   # new method + _pick_<method>
        return super()._selection_assign_method() + [('score', 'By score')]

    def _pick_score(self, lead, members):
        return members[:1].user_id, 'by score'
```

Create already routed leads from code:

```python
self.env['crm.lead'].with_context(crm_routing_auto=True, crm_routing_rule_id=rule.id).create(vals)
```

## Tests

```bash
odoo-bin -d <db> -i crm_lead_routing --test-tags=/crm_lead_routing --stop-after-init
```

## License

LGPL-3. Author: mangrovex (Manuel Vega Ulloa).
