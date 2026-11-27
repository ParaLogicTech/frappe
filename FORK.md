# How this fork differs from Frappe v15

Differences between ParaLogic's fork and upstream [frappe/frappe](https://github.com/frappe/frappe) `version-15`, for
developers and coding agents. **Where this file contradicts upstream documentation, this file is right.** The upstream
base version is the first part of `__version__` in `frappe/__init__.py`. Paths are relative to `frappe/`.

```bash
git fetch https://github.com/frappe/frappe version-15
git diff --stat FETCH_HEAD...version-15
```

## Changed upstream behaviour

Read this first: these differences are the most likely to surprise someone who knows stock Frappe.

### Relaxed or disabled checks

- **Deleted Document restore** doesn't require System Manager; it still requires create permission on the DocType
  and read permission on the document. Bulk restore still requires System Manager.
  (`core/doctype/deleted_document/deleted_document.py`)
- **Permission rows above level 0** don't need a level-0 row for the same role, so a role can grant field-level
  access only. Document access still comes from level-0 rows. (`core/doctype/doctype/doctype.py`)
- **`run_doc_method`** skips the docstatus-transition check on the document the client sends, so read permission is
  enough to call a whitelisted method on a submitted document (upstream also needs submit). The timestamp check stays
  and `save()` still checks transitions. (`handler.py`, `check_if_latest(check_docstatus_transition=)`)
- **Modules blocked on Administrator** are hidden for everyone except System Managers (upstream: everyone).
  (`config/__init__.py`)
- **Prepared reports** aren't switched on automatically after 15 s. (`core/doctype/report/report.py`)
- **Assignments**: closing or cancelling doesn't clear `assigned_to`, which is only set when it's a Link to User.
  (`desk/form/assign_to.py`)
- **Saving a User** doesn't update the existing Contact's name or numbers. (`core/doctype/user/user.py`)
- **`/apps`** is bypassed: the default path after login is always `/app`. (`apps.py`)
- **Integration Request** logs aren't auto-cleared (upstream: 90 days). (`hooks.py`, `default_log_clearing_doctypes`)
- **Received emails** reopen an Issue only when it's Replied, like other DocTypes (upstream: from any status).
  Feedback and Automated Message communications don't update the parent at all.
  (`core/doctype/communication/communication.py`)
- **Website top bar**: a parent item may have both a URL and children. (`website/doctype/website_settings/`)
- **Query report export**: Currency columns aren't rounded to their precision, and CSV keeps ISO dates instead of the
  system date format. (`desk/query_report.py`, `format_fields`)
- **Naming-series validation** doesn't log errors. (`core/doctype/document_naming_settings/`)
- Upstream patches `v15_0.set_contact_full_name` and `v16_0.add_app_launcher_in_navbar_settings` are commented out.

### Different defaults

| Setting | Fork | Upstream |
|---|---|---|
| Time zone fallback (`utils/data.py`) | `Asia/Karachi` | `Asia/Kolkata` |
| First day of the week | Monday | Sunday |
| Time format (System Settings) | `12 Hour` / `24 Hour`, default `12 Hour` | format strings |
| `link_field_results_limit`, search page length | 20 | 10 |
| PDF margins (`utils/pdf.py`) | 8 mm | 15 mm |
| Alert sound volume | 0.5 | 0.2 |
| `make_property_setter(is_system_generated=)` | `False` | `True` |
| `bootinfo.error_report_email` (`boot.py`) | falls back to ParaLogic's address | no fallback |
| Contact / Address names | series `CONT-.#####` / `ADDR-.#####` | person or party name |

### Changed semantics and signatures

- **Mapper** (`model/mapper.py`):
  - `get_mapped_doc(explicit_child_tables=)`, and `source_doc` may be a Document.
  - Table-map `condition` / `filter` get `(source_d, source_doc, target_doc)`; `postprocess` gets `target_parent`;
    `table_maps["postprocess"]`.
  - `map_child_doc(target_d=)` maps into an existing row; `map_docs(method_supports_list=)`.
  - Args in `frappe.flags.args`; `frappe.flags.postprocess_after_mapping`.
- **`get_system_managers()`** (`utils/user.py`) returns plain addresses; `formatted_addresses=True` gives `Name <address>`.
- **`search_widget`** (`desk/search.py`): exact name match first, relevance by match position, formatted results (`format_values=1`).
- **`import_file_by_path`** (`modules/import_file.py`) re-imports when `modified` differs at all (upstream: only when newer). DocType shows
  "newer JSON" on any difference. Report `add_total_row` syncs from JSON.
- **Roles**: `Role.remove_roles` deletes only User and Role Profile rows. Role profiles add and remove their own roles
  without wiping others (`set_role_list`).
- **Contact**: primary/secondary email and mobile are synced with the child tables, replacing upstream's "only one
  primary" validation.
- `get_desk_link` uses `get_url_to_form` and shows the name.
- Version diffs compare formatted values (Int with thousand separators, Percent without `.00`).
- Website home page: hooks win over role home pages. (`website/utils.py`)
- Some return type hints are removed (`-> "Document"` on `get_doc`, `new_doc`, `insert`, …).
- **developer_mode** also lets Customize Form edit core and Single DocTypes, makes system-generated Custom Fields
  editable and renamable, and allows deleting standard navbar items.

## Fork features

### SMS

- **SMS Queue** (+ Recipient) and **SMS Template** are new; **SMS Log** is kept (upstream removed it). The scheduler
  flushes the queue and clears it daily.
- **SMS Settings**: `number_formatter`, `response_validation`, `error_message` (safe_eval code); `promotional` flag
  on parameters.
- **`send_sms`** takes a notification key, reference and party documents, a promotional flag and queueing options
  (send later, priority), via `queue_or_send_sms`. It creates a Communication per SMS and reports status per number.
- Hook `update_sms_request_params`; site config `enable_automated_sms`, `mute_sms` (`frappe.are_sms_muted()`);
  Desk `sms_manager.js`. OTP SMS use the same gateway and formatter, and the log hides the OTP.

### Notifications

- **Notification Count** (new): sends per document, child row, notification key and channel (Email, SMS, System
  Notification), with last scheduled/sent times. Desk: `frappe.get_notification_count(_str)`.
- **Notification** fields: `notification_key` (defaults to the name), `use_email_template` + `email_template`,
  `send_only_once`, `timeline_field`, `with_container`; jinja `recipient` on recipient rows. Conditions use safe
  globals.
- Controller hooks `validate_notification(notification_key, child_doctype, child_name, throw)` (block any channel) and
  `get_notification_attachment(notification_key)`; `has_notification()`.
- Child-row notifications: `doc.run_method(..., context=)`; `frappe.sendmail`, Email Queue and
  `enqueue_create_notification` carry `notification_key`, `child_doctype`, `child_name`;
  `enqueue_create_notification` also takes `enqueue_after_commit`.
  `make_notification_logs_for_role`.
- **Communication**: medium `WhatsApp`; Feedback and Automated Message on the timeline (realtime, with attachments);
  SMS delivery status; `make(timeline_doctype, timeline_name)`.
- **Activity feed**: `doc.get_feed()` → Activity Log via the `update_feed` doc event.

### Contacts, addresses and regional

- **Contact**: `email_id_2`, `mobile_no_2`, `tax_cnic`; whitespace cleaned, duplicates removed, numbers and IDs
  validated per country. Primary contact pushed to linked documents implementing `update_primary_contact`. Extended
  `get_contact_details`; `get_all_contact_nos`, `add_phone_no_to_contact`; rewritten `contact_query`.
- **Address**: whitespace clean-up, `address_title` from the first link; primary address pushed to linked documents
  implementing `update_primary_address`. `get_default_address(primary_only, shipping ordering)`, whitelisted
  `get_company_address(shipping_address)`, portal list via the user's contact links, rewritten `address_query`.
- Desk: `address_and_contact.js` (number selects and dialogs), Contact and Address quick entry.
- **`frappe.regional`** (`regional/`): mobile and tax ID formatting and validation for Pakistan and UAE; duplicate tax
  ID / mobile / email checks.

### Printing and signatures

- **Signed Document**, **Signed Document Signatory**, **Print Format Signatory**, **Digital Signature Settings**
  (`printing/doctype/`): signatures drawn in the print view and stamped into the PDF; optional digital signing
  (pyhanko).
- Print Format `css_file_path`, `signatories`; hook `print_include_css`; Print Settings `print_as_primary_button`.
- PDF: wkhtmltopdf options as `.print-format` rules in CSS comments, `footer-spacing`, Custom page size fix. File names
  include the document title; multi-PDF downloads take `filename`; raw printing gets `args`.
- Templates are looked up in the print format's module first. Letter heads render with jinja in boot.
  `get_print_settings` goes through `run_method` and can show the document's fields.

### Documents and model

- **Auto Value Setter** (new; per DocType via `allow_auto_value_setter`): sets field values from conditions before
  insert and save, on parent and child rows.
- **Document**: `flags.disallow_on_submit` + `get_fields_for_disallow_on_submit()` lock allow-on-submit fields per
  document; `before_validate_links` hook; `has_method(doctype, method)`; `update_if_missing(force_fields)`;
  `round_floats_in(excluding=)`; `get_formatted(precision, negative_value)`; module-level `notify_doc_update()`;
  `db.set_value(notify=True)`.
- **Naming**: `()` allowed in series; `series_value_field` stores or reuses the number in a field; date parts from
  `doc.creation`; naming rules skip child tables.
- **Queries**: `subtree of` / `not subtree of` filters; `DatabaseQuery(additional_conditions=)`.
- `frappe.utils.status_updater.StatusUpdater` (completion %, over-allowance) for apps to share.
- Hooks `additional_doctype_permissions`, `update_website_list_data`; `meta.get_label(default)`;
  `frappe.catch_realtime_msgprint`; `get_fetch_values(skip_fetch_if_empty)`; workflow `update_value = "__user"`;
  ToDo `title`; Server Script event `On Change`.

### Reports, lists and Desk

- **Grouped reports**: `group_report_data`, `flatten_grouped_report_data`, `hide_columns_if_filtered`,
  `group_report_data_in_printable_format`; `with_total_row`, `_excludeFromTotal` rows, columns with
  `ignore_user_permissions`.
- **Export** sends the data on screen (`report_data` / `visible_columns`) instead of re-running the report; Excel gets
  number and date formats and a frozen header. Report view cells can be edited inline.
- **Dashboard Chart**: child-table charts (`parent_document_type`), group-by limit.
- **Desk UI**: grid additions (move selected rows, per-row field properties, columns on editable grids, focus
  helpers), multi-select dialog banner and filters, list paging button, standard filters from child tables and tree
  links, form indicator formatter, richer `frappe.format` options, Google Maps geolocation, signature pad, treeview
  realtime updates, and fork SCSS across Desk, print preview, dark mode and website.

### Website

- **Contact Us**: query options table (Contact Query Option), map iframe/URL, confirmation email template, extra
  fields (escaped) in the forwarded email, `send_message` POST only, `process_contact_message`; settings reach every
  page via `update_website_context`.
- `google_tag_manager_id`; analytics only outside developer mode.
- Web lists: `list_count`, row `idx`, reworked `list.js` with reload/load-more events. `navbar_class` in the page
  context replaces the fixed `navbar-light`.
- Email Group `require_email_verification`; Portal Menu Item `icon`; web forms without a Website Sidebar; Blog Post
  `blogger` optional (left join).

### Integrations, security and admin

- Google Drive backups auto-delete old backups; Google Settings Maps.
- Integration Request: `ip_address`, `url` index, empty JSON stored as NULL.
- Role `bypass_two_factor_auth`. Role "Impersonation User" may `impersonate` (not yourself, Administrator or Guest).
- Site config `allowed_embedding_domains` (CSP `frame-ancestors`), `default_cookie_samesite`; `get_url` honours
  `host_name`.
- Utils: `clean_whitespace`, `sanitize_whitespace`, `round_half_up` / `round_half_down` / `round_half_away_from_zero`, `round_up` /
  `round_down`, `combine_datetime`, `original_name` helpers, `fmt_money(force_symbol)` + DocField
  `force_currency_symbol`, `get_link_to_form(target)`, `strip_html(repl)`.
- Jinja and Server Script globals add `datetime`, `len`, `cint` / `cstr` / `flt`, `get_cached_value`, `sorted` and
  the `original_name` helpers. Templates rendered with `restrict_globals=True` keep upstream's read-only document
  helpers.
- Fixtures: `sync_fixtures(force)`, export keeps `creation`, Custom Fields exported as system generated. `migrate`
  reloads the core DocType DocTypes first.

### Packaging and patches

- Version `<upstream>+pl.<n>`; releases via the Prepare Release and Publish Release workflows. Upstream's release
  workflows and `.releaserc` are deleted.
- Dependencies `pyhanko`, `signature_pad`; `@paralogic/frappe-datatable` and `@paralogic/air-datepicker` replace the
  upstream packages.
- Fork patches in `patches.txt`, including the `notification_type` → `notification_key` rename.

## Backports

Kept byte-identical to upstream.

- Network printing `print_by_server` (letterhead parameter, `no_letterhead` inversion, `_lang`) from develop
  `9f67e077ff`. (`printing/page/print/print.js`, `utils/print_format.py`)

"(backport #…)" commits in older history are from v14 and already in upstream v15.

## Keeping this file current

- A PR that adds a fork feature, changes upstream behaviour or backports upstream code updates this file.
- After an upstream merge, remove entries upstream now has.
- No client names, client apps or client data.
