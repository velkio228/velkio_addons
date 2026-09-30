# Velkio State Based Access

Configure view behavior as records move through their workflow. The engine
processes form, list and kanban views for matching users, groups and companies.

**Odoo 19 · Community and Enterprise · Technical name:** `velkio_state_based_access`

## What you can control

Create a rule for a model, its state field, and the users, groups, and companies
it applies to. Choose one or more state values; leave the state list empty to
apply the rule in every state.

| Rule | Interface behavior |
|---|---|
| Field restriction | Hide a field, make it read-only, or require it |
| Page restriction | Hide selected notebook tabs |
| Button restriction | Hide selected header, action, object, or smart buttons |
| Whole form | Make every form field read-only |
| Chatter | Hide the chatter |

Field, page, button, and whole-form behavior can depend on the selected states.
Chatter visibility is configured per rule and is not state-dependent.

## Set up a rule

1. Install the module, grant rule maintainers **State Based Access / Manager**, and open **State Based Access → Access Rules**.
2. Create a rule and choose a model. The `state` field is selected when available.
3. Select the state values, users or groups, and any applicable companies.
4. Add field, page, button, whole-form, or chatter restrictions and save.

When neither users nor groups are selected, the rule applies to all users in its
selected companies. The state and view-node choices can be refreshed with the
**Sync States & Nodes** action.

## View coverage and matching

- **Form:** field modifiers, named buttons, notebook tabs, whole-form read-only,
  and chatter visibility.
- **List:** modifiers on matching fields and named buttons. Per-record invisibility
  does not hide the entire column; editable behavior depends on the view/widget.
- **Kanban:** modifiers on matching field and named button nodes. Their effect
  depends on the card template and widget; this is not a whole-card editing lock.
- Search views and nested relational subviews are not rewritten by a parent rule.

Users match by explicit user **or** group membership, including inherited groups.
Company matching uses the currently active company. Matching restrictions combine
with existing modifiers; a later sequence does not override an earlier restriction.
The form configuration picker offers stored fields. State/node synchronization
adds missing choices; it does not rebuild or remove all stale entries.

## Important security boundary

This module changes the view interface for users. Hidden or read-only controls
are not server-side authorization. Use Odoo access rights (ACLs) and record rules
to protect data and operations on the server.

The administrator is not automatically exempt from matching rules. Scope rules
deliberately and verify administrator access in your database. Many2one state
fields expose up to 1,000 related state values for selection.

## Compatibility and support

- Odoo 19.0, Community or Enterprise
- Dependencies: `base`, `web`, `mail`
- License: OPL-1
- Publisher: Velkio – Odoo Solutions · <https://velkio.com>
- Support: <mailto:velkio.odoosolution@gmail.com>
