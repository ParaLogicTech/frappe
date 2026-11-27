# How this fork differs from Frappe v15

This file lists the differences between ParaLogic's fork and upstream [frappe/frappe](https://github.com/frappe/frappe)
`version-15`. It is written for developers and for coding agents: **if something here contradicts upstream
documentation, this file is right for this repository.**

- The upstream version the fork is based on is the first part of `__version__` in `frappe/__init__.py`.
- Sections: [changed upstream behaviour](#changed-upstream-behaviour) (read this first),
  [fork features](#fork-features), [backports](#backports), [keeping this file current](#keeping-this-file-current).

To see the current difference yourself:

```bash
git fetch https://github.com/frappe/frappe version-15
git diff --stat FETCH_HEAD...version-15
```

---

## Changed upstream behaviour

Upstream code the fork edits, disables or re-defaults. These are the differences most likely to surprise someone who
knows stock Frappe.

### Relaxed or removed checks

| Change | Where | Effect |
|---|---|---|
| Restoring a Deleted Document doesn't require System Manager | `core/doctype/deleted_document/deleted_document.py` (`restore`) | Restoring still requires create permission on the document's DocType and read permission on the document. Bulk restore still requires System Manager. |
| permlevel > 0 permission rows allowed without a level-0 row for the same role | `core/doctype/doctype/doctype.py` (`validate_permissions`) | A role can grant only field-level access, e.g. to users who get document access (level 0) from another role. Document access still needs a level-0 row. |
| `run_doc_method` doesn't check docstatus transitions on the document the client sends | `handler.py`, `model/document.py` (`check_if_latest(check_docstatus_transition=)`) | Read permission is enough to call a whitelisted method on a submitted document; upstream also requires submit permission. The timestamp check stays, and saving still checks transitions. |
| System Managers ignore modules blocked for Administrator | `config/__init__.py` | Modules blocked on the Administrator user are hidden for everyone except System Managers; upstream hides them for everyone. |
| Naming-series validation doesn't log errors | `core/doctype/document_naming_settings/document_naming_settings.py` | |

### Disabled upstream behaviour

| Change | Where | Effect |
|---|---|---|
| Reports don't switch to prepared reports automatically after 15 s | `core/doctype/report/report.py` | Slow reports keep running in the request. |
| Closing or cancelling an assignment doesn't clear `assigned_to` | `desk/form/assign_to.py` | `assigned_to` is only set when it is a Link to User. |
| Saving a User doesn't update the existing Contact's name or numbers | `core/doctype/user/user.py` | Contact data is managed on the Contact. |
| `/apps` page bypassed | `apps.py` | The default path after login is always `/app`. |
| Integration Request logs aren't auto-cleared | `hooks.py` (`default_log_clearing_doctypes`) | Upstream clears them after 90 days. |
| A received email reopens an Issue only when it is Replied | `core/doctype/communication/communication.py` (`update_parent_document_on_communication`) | Same rule as other DocTypes; upstream reopens an Issue from any status. Feedback and Automated Message communications don't update the parent document at all. |
| Website top bar: a parent item may have a URL and children | `website/doctype/website_settings/` | Upstream rejects a parent item with a URL. |
| Query report export: Currency columns aren't rounded to their precision; CSV keeps ISO dates | `desk/query_report.py` (`format_fields`) | Upstream rounds Currency columns that set a precision, and writes CSV dates in the system date format. |
| Upstream patches `v15_0.set_contact_full_name` and `v16_0.add_app_launcher_in_navbar_settings` commented out | `patches.txt` | |

### Different defaults

| Setting | Fork | Upstream |
|---|---|---|
| Time zone fallback | `Asia/Karachi` (`utils/data.py`) | `Asia/Kolkata` |
| First day of the week | Monday | Sunday |
| System Settings time format | options `12 Hour` / `24 Hour`, default `12 Hour` | format strings |
| `link_field_results_limit`, search page length (`core/doctype/system_settings/`) | 20 | 10 |
| PDF margins (`utils/pdf.py`) | 8 mm | 15 mm |
| Alert sound volume | 0.5 | 0.2 |
| `make_property_setter(is_system_generated=...)` (`custom/doctype/property_setter/`) | `False` | `True` |
| `bootinfo.error_report_email` | falls back to ParaLogic's address (`boot.py`) | no fallback |
| Contact / Address names | naming series `CONT-.#####` / `ADDR-.#####` | named after the person or party |

### Changed semantics and signatures

- **Document mapper** (`model/mapper.py`): signatures differ from upstream.
  - `get_mapped_doc(..., explicit_child_tables=...)`; `source_doc` may be a Document.
  - Table-map `condition` / `filter` receive `(source_d, source_doc, target_doc)`; `postprocess` receives
    `target_parent`; `table_maps["postprocess"]` exists.
  - `map_child_doc(..., target_d=...)` can map into an existing row. `map_docs(method_supports_list=...)`.
  - Mapper args are available in `frappe.flags.args`; `frappe.flags.postprocess_after_mapping`.
- **`get_system_managers()`** (`utils/user.py`) returns plain email addresses. Pass `formatted_addresses=True` for
  upstream's `Name <address>` form.
- **`search_widget`** (`desk/search.py`): an exact name match comes first, relevance is the position of the match,
  and results are formatted (`format_values=1`).
- **`import_file_by_path`** (`modules/import_file.py`) re-imports when `modified` differs at all (upstream: only when
  the file is newer). DocType shows the "newer JSON" message on any difference. Report `add_total_row` is synced from
  JSON.
- **Roles**: `Role.remove_roles` deletes only User and Role Profile rows; role profiles update user roles without
  wiping extra rows (`set_role_list`).
- **Contact** "only one primary" validation is replaced by syncing primary and secondary email/mobile with the child
  tables (see [Contacts and addresses](#contacts-addresses-and-regional)).
- `get_desk_link` uses `get_url_to_form` and shows the name.
- Version diffs compare formatted values; Int values are formatted with thousand separators; Percent drops `.00`.
- Website home page (`website/utils.py`): hooks take priority over role home pages.
- Some public return type hints are removed (`-> "Document"` on `get_doc`, `new_doc`, `insert`, …).

### developer_mode does more

- Customize Form can customize core and Single DocTypes.
- System-generated Custom Fields become editable and renamable.
- Standard navbar items can be deleted.

---

## Fork features

Things upstream doesn't have. Paths are relative to `frappe/`.

### SMS

- **SMS Queue** (+ SMS Queue Recipient), **SMS Template** (new) and **SMS Log** (kept; upstream removed it):
  `core/doctype/sms_queue/`, `core/doctype/sms_template/`, `core/doctype/sms_log/`. The scheduler flushes the queue
  and clears it daily.
- **SMS Settings**: `number_formatter`, `response_validation` and `error_message` (safe_eval code); parameters have a
  `promotional` flag.
- **API**: `send_sms` takes a notification key, reference and party documents, a promotional flag and queueing
  options (send later, priority), built on `queue_or_send_sms`. Creates a Communication per SMS (Automated Message when sent automatically) and reports
  success or failure per number.
- Hook `update_sms_request_params`. Site config `enable_automated_sms`; `mute_sms` → `frappe.are_sms_muted()`.
- Desk: `sms_manager.js` dialog.
- OTP SMS use the same gateway path and number formatter; the log hides the OTP.

### Notifications

- **Notification Count** (new, `core/doctype/notification_count/`): per document, child row, notification key and
  channel (Email, SMS, System Notification). Counts sends and records when each was last scheduled or sent. Updated by
  Email Queue, SMS and Notification Log. Desk: `frappe.get_notification_count(_str)`.
- **Notification** DocType: `notification_key` (defaults to the name), `use_email_template` + `email_template`,
  `send_only_once`, `timeline_field` (links the Communication to a party), `with_container`; recipient rows get a
  jinja `recipient` field. Conditions run with safe globals.
- **Controller hooks**: `validate_notification(notification_key, child_doctype, child_name, throw)` can block any
  channel; `get_notification_attachment(notification_key)` can replace attachments. `has_notification()` helper.
- `doc.run_method(..., context=...)` passes context into notifications (used for child-row notifications).
- `frappe.sendmail` and Email Queue carry `notification_key`, `child_doctype` and `child_name`.
- `enqueue_create_notification(..., notification_key, child_doctype, child_name, enqueue_after_commit)`;
  `make_notification_logs_for_role`.
- **Communication**: medium `WhatsApp`; Feedback and Automated Message types show on the timeline (realtime, with
  attachments); SMS delivery status from SMS Queue / SMS Log; `make(timeline_doctype, timeline_name)`.
- **Activity feed**: `doc.get_feed()` → Activity Log through the `update_feed` doc event on every DocType.

### Contacts, addresses and regional

- **Contact**: `email_id_2`, `mobile_no_2`, `tax_cnic`. Primary and secondary email/mobile are synced with the child
  tables. Whitespace is cleaned, duplicates removed and numbers/IDs validated per country. On save, the primary
  contact is pushed into linked documents that implement `update_primary_contact`. `get_contact_details` returns more;
  new `get_all_contact_nos`, `add_phone_no_to_contact`; rewritten `contact_query`.
- **Address**: whitespace clean-up; `address_title` from the first link. On save, the primary address is pushed into
  linked documents that implement `update_primary_address`. `get_default_address(primary_only, shipping ordering)`,
  whitelisted `get_company_address(shipping_address)`, portal address list through the user's contact links,
  rewritten `address_query`.
- Desk: `address_and_contact.js` (contact-number selects, add-number dialogs), Contact and Address quick entry.
- **`frappe.regional`** (new, `regional/`): mobile number and tax ID formatting and validation for Pakistan and UAE;
  duplicate tax ID / mobile / email checks.

### Printing and signatures

- **Signed Document**, **Signed Document Signatory**, **Print Format Signatory**, **Digital Signature Settings**
  (new, `printing/doctype/`): signatures drawn in the print view (signature_pad) and stamped into the PDF, with
  optional digital signing of the PDF (pyhanko).
- Print Format: `css_file_path`, `signatories`. Hook `print_include_css`. Print Settings: `print_as_primary_button`.
- PDF: wkhtmltopdf options can be set as `.print-format` rules inside CSS comments; `footer-spacing`; Custom page size
  fix. Download file names include the document title; multi-PDF downloads take `filename`. Raw printing gets
  `args`.
- Print template lookup checks the print format's own module first. Letter heads are rendered with jinja in boot.
- `get_print_settings` goes through `run_method` and can show the document's own fields.

### Documents and model

- **Auto Value Setter** (new, `core/doctype/auto_value_setter/`; enabled per DocType with `allow_auto_value_setter`
  on DocType and Customize Form): sets field values from conditions before insert and save, on parent and child rows.
- **Document**:
  - `flags.disallow_on_submit` + `get_fields_for_disallow_on_submit()` lock allow-on-submit fields per document.
  - `before_validate_links` hook, `Document.has_method(doctype, method)`, `update_if_missing(force_fields)`,
    `round_floats_in(excluding=)`, `get_formatted(precision, negative_value)`.
  - Module-level `notify_doc_update()`; `db.set_value(..., notify=True)`.
- **Naming**: `()` allowed in series; `series_value_field` stores or reuses the series number in a field; date parts
  come from `doc.creation`; naming rules skip child tables.
- **Queries**: nested-set filters `subtree of` / `not subtree of`; `DatabaseQuery(additional_conditions=)`.
- **`frappe.utils.status_updater.StatusUpdater`**: completion %, over-allowance checks, shared by apps.
- **Meta**: hook `additional_doctype_permissions`; `get_label(default)`.
- Hook `update_website_list_data`; `frappe.catch_realtime_msgprint` decorator;
  `get_fetch_values(skip_fetch_if_empty)`; workflow `update_value = "__user"`; ToDo `title`.
- Server Script event `On Change`.

### Reports, lists and Desk

- **Query reports**: server helpers `group_report_data`, `flatten_grouped_report_data`, `hide_columns_if_filtered`
  for grouped reports with group totals, printed with `group_report_data_in_printable_format`. `with_total_row`,
  `_excludeFromTotal` rows, columns with `ignore_user_permissions`.
- **Export** sends the data on screen (`report_data` / `visible_columns`) instead of re-running the report. Excel
  export gets column number and date formats and a frozen header row.
- Cells can be edited inline in report view.
- **Dashboard Chart**: charts on child tables (`parent_document_type`), group-by limit.
- **Desk UI**: grid additions (move selected rows, per-row field properties, column display on editable grids, focus
  helpers), multi-select dialog selection banner and filters, list paging button, standard filters from child tables
  and tree links, form indicator formatter, richer `frappe.format` options (css, indicator, link target/title,
  custom/global formatters), Google Maps geolocation (googlemutant), signature pad, treeview realtime updates.
- **Styling**: fork SCSS (buttons, grid, forms, lists, reports, print preview, dark mode,
  website).

### Website

- **Contact Us**: query options as a table (Contact Query Option), map iframe/URL, confirmation email template, extra
  form fields (escaped) in the forwarded email, `send_message` POST only, reusable `process_contact_message`. Settings
  reach every page through the `update_website_context` hook.
- Website Settings `google_tag_manager_id`; analytics are injected only outside developer mode.
- Web lists: `list_count`, row `idx`, reworked `list.js` with reload/load-more events.
- Navbar: `navbar_class` in the page context replaces the fixed `navbar-light` class.
- Email Group `require_email_verification`. Portal Menu Item `icon`. Web forms work without a Website Sidebar.
- Blog Post `blogger` is optional (blog list uses a left join).

### Integrations, security and admin

- Google Drive backups: auto-delete old database and file backups. Google Settings: Maps for geolocation.
- Integration Request: `ip_address`, `url` index, empty JSON fields stored as NULL.
- Role `bypass_two_factor_auth`.
- `impersonate` is also allowed for the role "Impersonation User" (not on yourself, Administrator or Guest).
- Site config: `allowed_embedding_domains` (CSP `frame-ancestors`), `default_cookie_samesite`; `host_name` is honoured
  by `get_url`.
- Utils: `clean_whitespace`, `sanitize_whitespace`, `round_half_up` / `round_half_down` / `round_half_away_from_zero`,
  `round_up` / `round_down`, `combine_datetime`, `original_name` helpers (strip the amendment suffix),
  `fmt_money(force_symbol)` + DocField `force_currency_symbol`, `get_link_to_form(target)`, `strip_html(repl)`.
- Jinja and Server Script globals add `datetime`, `len`, `cint` / `cstr` / `flt`, `get_cached_value`, `sorted` and the
  `original_name` helpers. Templates rendered with `restrict_globals=True` get upstream's read-only document helpers.
- Fixtures: `sync_fixtures(force)`; export keeps `creation`; Custom Fields are exported as system generated.
- `migrate` force-reloads the core DocType DocTypes first.

### Packaging, CI and patches

- Version `<upstream>+pl.<n>` in `frappe/__init__.py`. Releases come from the Prepare Release and Publish Release
  workflows (`.github/workflows/prepare-release.yml`, `publish-release.yml`). Upstream's release workflows and
  `.releaserc` are deleted.
- New dependencies: `pyhanko`, `signature_pad`. `@paralogic/frappe-datatable` and `@paralogic/air-datepicker` replace
  `frappe-datatable` and `air-datepicker`.
- Fork patches in `patches.txt`, including the `notification_type` →
  `notification_key` rename and the System Notification subject/message copy.

---

## Backports

Upstream code from newer branches, kept byte-identical to upstream.

| What | Upstream source | Where |
|---|---|---|
| Network printing `print_by_server`: letterhead parameter, `no_letterhead` inversion, `_lang` | develop `9f67e077ff` | `printing/page/print/print.js`, `utils/print_format.py` |

The "(backport #…)" commits in older fork history come from the v14 era and are already in upstream v15.

---

## Keeping this file current

- A pull request that adds a fork feature, changes upstream behaviour or backports upstream code updates this file in
  the same pull request.
- After merging an upstream release, remove entries upstream now has.
- Describe changes generically: no client names, client apps or client data.
