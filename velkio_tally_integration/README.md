# TallyPrime Connector

By Velkio Odoo Solutions. Version 19.0.1.2.1. License: LGPL-3.

Connect Odoo and TallyPrime for accounting and inventory synchronization. Choose which system owns each record type, follow outgoing records through a queue and review results inside Odoo.

## Requirements

Odoo 19 on Odoo.sh or on-premise, with custom Python add-ons enabled. Standard Odoo Online does not support these modules.

- Odoo 19 with Accounting/Invoicing, Inventory and the module’s listed dependencies.
- A working TallyPrime installation and company, with the XML gateway enabled. The default configured port is 9000.
- A network route from the Odoo server to the TallyPrime host for direct mode. On Odoo.sh, localhost refers to the cloud server, not your office PC.
- Tally access rights in Odoo for users, and manager rights for configuration and synchronization controls.

## Setup

1. **Prepare TallyPrime.** Start TallyPrime, open the correct company and enable its XML gateway. Confirm the configured port is available. Keep TallyPrime at the Gateway screen while synchronizing.

2. **Install and grant access.** Install TallyPrime Connector in Odoo. Give operators Tally user access and configuration owners Tally manager access.

3. **Create the connection.** Open Tally Prime → Dashboard & Instances → New. Set the Odoo company, Tally host, port, protocol and Tally company. Use Direct mode when Odoo can reach the gateway.

4. **Test and complete onboarding.** Select Test Connection. In Setup & Tools, review company discovery and onboarding. Choose whether to import the chart of accounts or map to an existing chart, and set the required history and opening settings.

5. **Choose ownership and direction.** Review Sync Rules and What Syncs. Enable only the record types you need and decide which system wins when both systems change a record.

6. **Synchronize and inspect results.** Start with Get Masters Only and verify mappings. Then use Sync Now for the configured flow. Review Odoo → Tally, Tally → Odoo, Waiting, Failed and All Logs. Configure automatic imports after validating the first run.

## Scope

Actual processing depends on the enabled record types, direction, ownership, account mappings and connection settings. Direct mode requires a reachable TallyPrime XML gateway. Agent mode requires a separately deployed on-premise relay; an agent executable is not bundled in this module.

## Frequently asked questions

**Is TallyPrime included?**

No. This is an Odoo connector. You need your own working TallyPrime installation and an accessible XML gateway.

**Does it work with Odoo.sh?**

The module can be deployed on Odoo.sh. Direct mode still needs a reachable TallyPrime endpoint. An office-only address or localhost will not connect a cloud server to your PC.

**Do I need an agent?**

Direct mode connects from Odoo to TallyPrime without an agent. Agent mode is available for a separately deployed relay; the relay executable is not included in this add-on.

**How often does automatic sync run?**

The direct-sync scheduled action is configured for every two minutes. Automatic pulls also depend on the instance’s automatic-import setting and pull interval. Actual timing depends on the Odoo scheduler and gateway availability.

**Which system wins when both records change?**

The entity’s source-of-truth and direction settings control processing. Review these settings before enabling two-way synchronization.

**What happens to failed records?**

Outgoing records can be reviewed in the queue and logs. Repeated inbound failures can enter quarantine, where an operator can review and retry them.

**What data is exchanged?**

Enabled accounting, party, inventory and transaction records are exchanged with your configured TallyPrime endpoint according to their direction settings. Agent mode routes this traffic through your separately configured relay.

## Support

velkio.odoosolution@gmail.com

The marketplace presentation is in `static/description/index.html`.

Screenshots use demonstration data and a Tally simulator. They predate the Precision navigation icon.
