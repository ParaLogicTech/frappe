<div align="center">
	<h1>
		<br>
		<a href="https://frappeframework.com">
			<img src=".github/frappe-framework-logo.svg" height="50">
		</a>
	</h1>
	<h3>
		a web framework with <a href="https://www.youtube.com/watch?v=LOjk3m0wTwg">"batteries included"</a>
	</h3>
	<h5>
		it's pronounced - <em>fra-pay</em>
	</h5>
</div>

<div align="center">
	<a target="_blank" href="#license" title="License: MIT"><img src="https://img.shields.io/badge/License-MIT-success.svg"></a>
	<a target="_blank" href="https://www.python.org/downloads/" title="Python version"><img src="https://img.shields.io/badge/python-%3E=_3.11-success.svg"></a>
	<a href="https://frappeframework.com/docs"><img src="https://img.shields.io/badge/docs-%F0%9F%93%96-success.svg"/></a>
	<a href="https://github.com/ParaLogicTech/frappe/actions/workflows/server-tests.yml"><img src="https://github.com/ParaLogicTech/frappe/actions/workflows/server-tests.yml/badge.svg?branch=version-15"></a>
</div>

> [!NOTE]
> **This is ParaLogic's fork of the Frappe Framework.**
> Frappe is built and maintained by [Frappe Technologies](https://frappe.io) and its community; the original
> repository is [frappe/frappe](https://github.com/frappe/frappe). This fork is based on Frappe v15 and adds the
> changes ParaLogic's apps need. It is not an official Frappe release and is not supported by Frappe Technologies.

Full-stack web application framework that uses Python and MariaDB on the server side and a tightly integrated client
side library. Built for [ERPNext](https://erpnext.com).

## Table of Contents
* [How this fork differs](#how-this-fork-differs)
* [Installation](#installation)
* [Versions](#versions)
* [Keeping up with upstream](#keeping-up-with-upstream)
* [Compatibility](#compatibility)
* [Reporting issues](#reporting-issues)
* [Contributing](#contributing)
* [Resources](#resources)
* [License](#license)

## How this fork differs

The fork follows upstream `version-15` and adds to it. The main additions:

- **SMS**: a queue, templates and logs, per-number delivery status, and a Communication for every SMS sent.
- **Notifications**: notification keys, a per-document send count, "send only once", Email Template support, and
  notifications for child-table rows.
- **Contacts and addresses**: secondary email and mobile, per-country number and tax ID validation (Pakistan, UAE),
  and primary contact/address pushed into linked documents.
- **Printing**: signatures drawn on the print view and stamped into the PDF, optional digital signing, and
  wkhtmltopdf options set from print format CSS.
- **Data entry**: Auto Value Setter (field values from conditions), per-document locks on "allow on submit" fields,
  an extended document mapper, and naming series stored in a field.
- **Reports and Desk**: grouped reports with group totals, export of the data on screen, inline editing in report
  view, and many grid and list improvements.

Some upstream behaviour is also changed: different defaults (time zone `Asia/Karachi`, Monday as the first day of
the week, 12-hour time), a few checks relaxed, and a few function signatures extended.

**[FORK.md](FORK.md) lists every difference**, where it lives in the code and what it affects. Read it before you
rely on upstream documentation for anything listed there.

## Installation

Install [bench](https://github.com/frappe/bench) as described in the
[Frappe installation guide](https://frappeframework.com/docs/user/en/installation), then create a bench from this
fork instead of stock Frappe:

```bash
bench init --frappe-path https://github.com/ParaLogicTech/frappe --frappe-branch version-15 frappe-bench
```

To switch an existing bench to the fork:

```bash
bench remote-set-url https://github.com/ParaLogicTech/frappe
```

Then check out `version-15` in `apps/frappe` and run `bench update` (or `bench migrate` and `bench build` on each
site).

ParaLogic's apps (ERPNext fork, CRM and the product apps) require this fork; they won't run on stock Frappe.

## Versions

Releases are versioned `<upstream version>+pl.<n>`, for example `15.128.0+pl.1`: the Frappe release the fork is
based on, plus a ParaLogic build number that restarts at 1 for each upstream release. Releases are tagged
`v15.128.0+pl.1` and published on the [Releases](https://github.com/ParaLogicTech/frappe/releases) page.

`version-15` is the only maintained branch.

## Keeping up with upstream

- Upstream v15 releases are merged into `version-15` regularly. Each merge moves the base version and resets the
  build number.
- Fixes and features from newer upstream branches may be backported. Backported code is kept byte-identical to
  upstream, so later merges don't conflict. Backports are listed in [FORK.md](FORK.md#backports).
- Fixes that aren't specific to this fork should go to [frappe/frappe](https://github.com/frappe/frappe) as well.

## Compatibility

- Most apps written for Frappe v15 work on this fork. Check [FORK.md](FORK.md#changed-upstream-behaviour) if an
  app relies on the document mapper, `get_system_managers()`, Contact or Address naming, or the defaults listed
  there.
- Python 3.11+, MariaDB 10.6+, Node 18+, as for upstream v15.

## Reporting issues

- **Bugs in fork features or fork changes**: open an issue on
  [ParaLogicTech/frappe](https://github.com/ParaLogicTech/frappe/issues).
- **Bugs that also happen on stock Frappe**: report them to [frappe/frappe](https://github.com/frappe/frappe/issues).
- **Security issues**: don't open a public issue. Report them privately through
  [GitHub's private vulnerability reporting](https://github.com/ParaLogicTech/frappe/security/advisories/new).
  Issues that also affect stock Frappe go to [Frappe's security policy](https://frappe.io/security) as well.

## Contributing

1. Branch from `version-15` and open a pull request against `version-15` on this repository.
2. Add or update tests: the test suite is maintained and must pass in CI.
3. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org) (`fix: …`, `feat: …`).
4. **Update [FORK.md](FORK.md)** when a change adds a fork feature, changes upstream behaviour or backports
   upstream code.
5. Code backported from newer upstream branches stays byte-identical to upstream, with no added comments or style
   fixes, so later upstream merges don't conflict. Fork code follows frappe's style (ruff and prettier, line
   length 110).

Frappe's own [Code of Conduct](CODE_OF_CONDUCT.md) applies here too.

## Resources

1. [frappeframework.com](https://frappeframework.com) - Official documentation of the Frappe Framework. Where the
   fork differs, [FORK.md](FORK.md) takes precedence.
1. [frappe.school](https://frappe.school) - Courses by the Frappe maintainers and community.

## License

This repository is released under the [MIT License](LICENSE), like upstream Frappe. Copyright for the Frappe
Framework remains with Frappe Technologies Pvt. Ltd. and its contributors; ParaLogic's changes are released under the
same license. Third-party code is listed in [attributions.md](attributions.md).

By contributing to this fork, you agree that your contributions will be licensed under the MIT License.
