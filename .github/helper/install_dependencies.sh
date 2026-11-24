#!/bin/bash
set -e

echo "Setting Up System Dependencies..."

echo "::group::apt packages"
install_wkhtmltopdf() {
  wget -q --tries=3 --waitretry=5 --retry-connrefused https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.jammy_amd64.deb
  sudo apt-get -qq install -y --no-install-recommends ./wkhtmltox_0.12.6.1-2.jammy_amd64.deb
  wkhtmltopdf --version
}
# not in the background, so a failed install fails this step instead of tests that print PDFs
install_wkhtmltopdf
echo "::endgroup::"
