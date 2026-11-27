# Agent instructions

This repository is **ParaLogic's fork of the Frappe Framework**, based on upstream Frappe v15. It is not stock
Frappe.

## Read FORK.md first

[FORK.md](FORK.md) lists every difference from upstream: changed upstream behaviour, different defaults, changed
function signatures, fork-only features and backports. Upstream documentation, Stack Overflow answers and your own
knowledge of Frappe describe stock Frappe. Where FORK.md says otherwise, FORK.md is right for this repository.
When FORK.md doesn't cover something, read the code in this repository rather than assuming upstream behaviour.

## Rules for changes

- **Branch** from `version-15` and target `version-15` in pull requests.
- **Backports** from newer upstream branches stay byte-identical to upstream: no added comments, renames or style
  fixes, so later upstream merges don't conflict. Diff against the upstream file to confirm.
- **Fork code** follows frappe's style: tabs, double quotes, ruff format and prettier, line length 110.
- **Tests**: the test suite is maintained and CI must pass. Add or update tests for every change, and run the
  affected ones with `bench --site <test-site> run-tests --module <dotted.module>` on a site with only frappe
  installed.
- **FORK.md**: a change that adds a fork feature, changes upstream behaviour or backports upstream code updates
  FORK.md in the same pull request.
- **Commit messages** follow Conventional Commits (`fix: …`, `feat: …`, `docs: …`), one subject line.
- **No customer details**: don't name clients or quote client data in code, comments, commits or pull requests.
  Describe cases generically.
- **Version**: don't edit `__version__` by hand. Releases go through the Prepare Release workflow.
