# Velkio Odoo Dock

A personal app dock for the Odoo 19 backend, with pinned apps, recent apps and records, favourite menus, an application overview and appearance settings.

## Install or upgrade

Add this repository to your addons path, restart Odoo, update the Apps list and install **Velkio Odoo Dock**. For an existing installation, upgrade the module and reload the browser to load the updated assets. Version `19.0.1.1.1` fixes menu visibility, failed settings-save cancellation and outdated recent-record labels.

Settings are available from the dock's slider button. Each user chooses their own pinned apps. Version `19.0.1.1.2` removes the administrator Default Velkio Docks screen and group-default configuration.

Version `19.0.1.1.3` redesigns Dock Settings with Appearance and Behaviour tabs, compact visual choices, explanatory switch rows and a fixed action footer. Settings still preview live, and Cancel restores unsaved appearance changes.

Version `19.0.1.1.5` keeps the dock visible on the Enterprise home screen and hides the default app grid on desktop. Use the dock's Show Applications button to browse all apps. Auto-hide resumes inside apps. Small screens retain Odoo's normal home grid because the dock is hidden there.

Version `19.0.1.1.6` adds a home workspace with today's date, app search, shortcuts for pinning apps and dock settings, and up to five recent records. It appears only on the desktop home screen and uses the existing personal record history.

Version `19.0.1.1.7` adds the active company's configured logo, a clock updating every second in the browser's local time, and a greeting using the logged-in user's name. Greetings change at 05:00, 12:00, 17:00 and 21:00. Recent apps appear at the bottom when enabled in dock settings. Set the company logo in Odoo's company settings.

Version `19.0.1.1.8` fixes workspace contrast in Odoo light mode. Text, cards, borders and icons follow Odoo's colour scheme independently of the overview theme setting.

## Permission behavior

Pins, favourites and recent apps are filtered with Odoo's menu visibility rules for the current user. Previously saved pins are rechecked when the dock loads. Recent records are returned only while the user can still read them, and their current display names are used. The dock does not grant additional business-record access.

## Tests

Run the backend suite on a separate Odoo 19 test database with `--test-enable --test-tags=/velkio_odoo_dock`. The tests run after the full module registry has loaded. Never use your production database for automated tests.

Run the settings dialog's failure/success regressions with:

```bash
node velkio_odoo_dock/tests/test_settings_save.mjs
```

The October 7 verification passed 14 backend tests on both a fresh minimal installation and an upgrade with mail/Contacts/To-do installed, plus 27 Firefox browser checks. Enterprise-specific home-menu behavior and other browsers were not certified by this run.

The default-dock removal in version `19.0.1.1.2` passed the current 13-test backend suite and an upgrade check confirming that personal pins and preferences are preserved.
