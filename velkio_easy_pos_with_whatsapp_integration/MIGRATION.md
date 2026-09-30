# Existing-database migration

This merged folder supports fresh installations. It preserves the original
model/table names so an existing database can be migrated without copying bills
into new tables. Module XML IDs, view references, assets and ownership still need
migration when the installed technical name changes.

Do not uninstall `pos_screen` or `pos_screen_whatsapp` from a database containing
bills to install the new name: uninstall can remove application records.

A safe migration must be prepared and validated on a backup clone:

1. Back up the database and filestore; retain both original source folders.
2. Inventory bills, lines, counters, payment methods, groups, report/template
   settings and any other addons depending on the old names.
3. Move old external-ID ownership to the new module namespace, resolving
   collisions by checking that the IDs point at the same records. Preserve
   external references used by other installed addons.
4. Update installed-module/dependency metadata so the merged module owns the
   existing models, and the original providers are not loaded concurrently.
5. Upgrade the merged provider and restart Odoo. Check schema constraints first:
   existing negative lines require a refund migration decision because the new
   counter accepts positive sale quantities.
6. Verify counts, groups, company rules, sequences, receipt templates, historic
   WhatsApp links and historical paid totals. Run tests and a cashier transaction
   before switching the live instance.

No existing/live database migration was executed as part of this build. The
installation hook prevents accidental installation alongside active originals.
