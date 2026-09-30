# Odoo 17 app presentation

Both modules use the Velkio Precision publisher logo in their page headers, support areas and illustrated banners. Application icons are product-specific: a bell and clock for Reminders & Notifications, and a shield and lock for Simplify Access Management. No Velkio logo is used as an application icon.

The index pages use inline layout styles and responsive images, with no external stylesheet or JavaScript dependency. Each page includes supported features, scope, prerequisites, six setup steps, workflow, a product walkthrough, documentation, troubleshooting, FAQs and support.

## Rebuild and validate

```bash
python3 tools/build_app_presentation.py --module reminders --output velkio_reminders_notification/static/description
python3 tools/build_app_presentation.py --module access --output velkio_simplify_access_management/static/description
python3 tools/check_app_presentation.py velkio_reminders_notification velkio_simplify_access_management
python3 tools/package_apps.py
```

The package is written to `release/odoo-apps-17.0.zip`. Old marketing assets and caches are excluded from the archive. Git contains the build tools and approved artwork; release artifacts are ignored.

## Before posting to Odoo Apps

Upgrade each module on a separate Odoo 17 test database to refresh the app-menu icon. The code behavior and module versions are preserved by this presentation update. Installation or upgrade has not been tested on a live database during this task.

Reminders retains its existing demonstration images. Access Studio retains its existing illustrated UI mockups, explicitly labeled in the page. Capture actual Access Studio screens from a test database before describing those images as screenshots. Neither marketing banner is a screen capture.

Check desktop and mobile presentation, and verify reminder delivery, manager permissions, access rules and company scope using separate test accounts. This local package does not publish to Odoo Apps or push to GitHub. OPL modules are priced at USD 1.00. LGPL modules remain free; licenses are preserved.

## Artwork

The four new raster images were generated with the built-in image generation tool. Exact production prompts are saved in `artwork/branding/presentation-prompts.md`. Icon masters are resized to 512 × 512 for the module assets; banners retain their generated resolution.

All application display names use the Velkio prefix.
