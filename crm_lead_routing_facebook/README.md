# Facebook Lead Ads Sync (`crm_lead_routing_facebook`) — Odoo 19

Downloads the leads of your Facebook Lead Ads forms and hands them over to
[Smart Lead Routing](../crm_lead_routing).

## Setup

1. *CRM ▸ Configuration ▸ Settings ▸ Facebook Lead Ads*: App ID, App Secret, Graph API URL
   (default `https://graph.facebook.com/v26.0`) and lookback days.
2. Add `<your Odoo URL>/crm_lead_routing_facebook/auth` as a valid OAuth redirect URI in your Facebook App.
3. **Get Access Token** → Facebook redirects back and the token is exchanged for a long-lived one.
4. **Import Pages** → on each page, **Import Forms** (reads the questions and proposes the default mapping).
5. Enable **Fetch Leads** on the forms. The hourly scheduled action
   *CRM: fetch Facebook Lead Ads leads* (or the form button) creates the leads.

Each lead gets the **Facebook Lead Ads** inbound channel, campaign, ad set and ad (as UTM medium).
Answers that are not mapped go to the lead notes. `country` and `state` answers are matched by name or code.

## Routing

- Routing rules can filter by the *Facebook Lead Ads* channel and by **Facebook Forms**.
- **Forced rule** (per form): always apply that rule.
- **Fallback team** (per form): when no rule matches, assign that team and its leader.

## External service

The module calls the Meta Graph API (`graph.facebook.com`) only after an administrator enters the
credentials. Tokens are stored in the database and are only visible to administrators.

## Tests

```bash
odoo-bin -d <db> -i crm_lead_routing_facebook --test-tags=/crm_lead_routing_facebook --stop-after-init
```

The tests mock the Graph API; no network or credentials are needed.

## Credits and license

Based on `crm_facebook_leads` by BADEP and Vauxoo (AGPL-3), rewritten for Odoo 19 by mangrovex
(Manuel Vega Ulloa). Licensed under AGPL-3.
