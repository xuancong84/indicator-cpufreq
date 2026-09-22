#!/bin/bash
# Installs indicator-cpufreq system-wide from this checkout.
#
# setup.py (DistUtilsExtra.auto.setup) only handles the Python package,
# scripts, desktop file, policy file and translations; it doesn't install
# the D-Bus system-service activation files under data/, and requires
# python3-distutils-extra to even run. This script installs everything
# setup.py would, plus those D-Bus files, using only coreutils/gettext,
# which are present on any Debian/Ubuntu desktop.
#
# Usage: sudo ./install.sh

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
	echo "This script installs system-wide files; please run it as root (sudo ./install.sh)." >&2
	exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SITE_PACKAGES="$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"

echo "Installing indicator_cpufreq Python package to $SITE_PACKAGES ..."
install -d -m755 "$SITE_PACKAGES/indicator_cpufreq"
install -m644 indicator_cpufreq/__init__.py indicator_cpufreq/cpufreq.py indicator_cpufreq/indicator.py \
	"$SITE_PACKAGES/indicator_cpufreq/"

echo "Installing executables to /usr/bin ..."
install -Dm755 bin/indicator-cpufreq /usr/bin/indicator-cpufreq
install -Dm755 bin/indicator-cpufreq-selector /usr/bin/indicator-cpufreq-selector

echo "Installing tray icons ..."
install -d -m755 /usr/share/icons/ubuntu-mono-dark/status/22
install -d -m755 /usr/share/icons/ubuntu-mono-light/status/22
install -d -m755 /usr/share/icons/hicolor/22x22/status
install -m644 icons/ubuntu-mono-dark/* /usr/share/icons/ubuntu-mono-dark/status/22/
install -m644 icons/ubuntu-mono-light/* /usr/share/icons/ubuntu-mono-light/status/22/
# also into hicolor, matching setup.py's workaround for LP: #1125598
install -m644 icons/ubuntu-mono-dark/* /usr/share/icons/hicolor/22x22/status/
if command -v gtk-update-icon-cache >/dev/null; then
	gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

# Desktop entry and PolicyKit policy are gettext .in templates: fields
# prefixed with '_' are translatable. Use intltool-merge for full
# translations when available, otherwise just drop the '_' prefixes so the
# untranslated (English) template still installs as a valid file.
merge_translatable() {
	local mode="$1" src="$2" dest="$3"
	if command -v intltool-merge >/dev/null; then
		intltool-merge -q "$mode" po "$src" "$dest"
	elif [ "$mode" = "-x" ]; then
		# XML (e.g. PolicyKit .policy): translatable elements are tagged
		# <_foo>...</_foo>; drop the leading underscore on the tag name.
		sed -E 's/<(\/?)_/<\1/g' "$src" > "$dest"
	else
		# desktop entry: translatable keys are prefixed, e.g. _Name=...
		sed 's/^_//' "$src" > "$dest"
	fi
}

echo "Installing desktop entry ..."
install -d -m755 /usr/share/applications
merge_translatable -d indicator-cpufreq.desktop.in /usr/share/applications/indicator-cpufreq.desktop
chmod 644 /usr/share/applications/indicator-cpufreq.desktop

echo "Installing PolicyKit action ..."
install -d -m755 /usr/share/polkit-1/actions
merge_translatable -x indicator_cpufreq/com.ubuntu.indicatorcpufreq.policy.in \
	/usr/share/polkit-1/actions/com.ubuntu.indicatorcpufreq.policy
chmod 644 /usr/share/polkit-1/actions/com.ubuntu.indicatorcpufreq.policy

echo "Installing D-Bus system-service activation files ..."
install -Dm644 data/com.ubuntu.IndicatorCpufreqSelector.service \
	/usr/share/dbus-1/system-services/com.ubuntu.IndicatorCpufreqSelector.service
install -Dm644 data/com.ubuntu.IndicatorCpufreqSelector.conf \
	/etc/dbus-1/system.d/com.ubuntu.IndicatorCpufreqSelector.conf

if command -v msgfmt >/dev/null; then
	echo "Installing translations ..."
	for po in po/*.po; do
		lang="$(basename "$po" .po)"
		install -d -m755 "/usr/share/locale/$lang/LC_MESSAGES"
		msgfmt -o "/usr/share/locale/$lang/LC_MESSAGES/indicator-cpufreq.mo" "$po"
	done
else
	echo "msgfmt not found, skipping translations (app still works, just untranslated)." >&2
fi

# Let dbus-daemon pick up the new system.d policy without a reboot.
if command -v systemctl >/dev/null && systemctl is-active --quiet dbus 2>/dev/null; then
	systemctl reload dbus || true
fi

echo
echo "Done. If indicator-cpufreq is already running, restart it to pick up the update:"
echo "  killall indicator-cpufreq indicator-cpufreq-selector 2>/dev/null; indicator-cpufreq &"
