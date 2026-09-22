# indicator-cpufreq

A system tray applet for viewing and changing CPU frequency scaling on Linux. Originally a port
of GNOME's CPU frequency applet for Ubuntu/Unity; this fork has been updated to also work on
modern `intel_pstate`/`amd-pstate` systems and KDE Plasma (X11 and Wayland).

## Features

- Shows current CPU frequency in the tray icon (optionally as text next to the icon, `-f`).
- **Left-click** the tray icon: choose a maximum CPU frequency or scaling governor
  (`performance`, `powersave`, `ondemand`, `conservative`, depending on what your driver
  supports). On laptops whose firmware exposes an ACPI platform profile (`/sys/firmware/acpi/
  platform_profile`) — the "fan/cooling policy" also known on some vendors as a thermal/Silent-
  Balanced-Performance mode — this is auto-detected and added as a third choice group in the same
  menu (e.g. Quiet / Balanced / Performance). It's simply absent if your firmware doesn't expose
  it.
- **Right-click** the tray icon: enable or disable individual CPU cores. Cores are grouped by
  their hardware frequency range (e.g. performance cores vs. efficiency cores on a hybrid CPU, or
  cores with a different max clock in an asymmetric AMD design); checking/unchecking a group's
  header toggles every core in that group at once. The menu stays open across multiple clicks, so
  you can flip several boxes before dismissing it (via the "Close" item or clicking outside).
- Safe to disable cores: before the system suspends, any core you've disabled is automatically
  re-enabled (some hardware/driver combinations hang or misbehave on resume otherwise), and it's
  put back offline again once the system wakes up.
- Actual frequency/governor/core changes are done by a small privileged helper over D-Bus, so the
  tray application itself never needs to run as root.

Left-click and right-click showing different menus isn't something the AppIndicator3/libappindicator
library supports (it always shows the same menu for either button) — this app instead speaks the
`org.freedesktop.StatusNotifierItem` D-Bus protocol directly, which is what lets the two clicks
diverge. This works out of the box on KDE Plasma (X11 and Wayland). On GNOME Shell you'll need the
[AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/)
extension, since GNOME Shell doesn't implement a status-notifier host itself — the same is true
whether or not an app uses this trick.

## Requirements

- Python 3, GTK 3 via PyGObject (`python3-gi`)
- `python3-dbus`, `python3-psutil`
- `libcpufreq0` (used via `ctypes`; falls back to reading/writing sysfs directly under
  `/sys/devices/system/cpu/cpuN/cpufreq/` when the driver doesn't expose a discrete
  `scaling_available_frequencies` list, e.g. `intel_pstate`/`amd-pstate`)
- `policykit-1` (privileged actions are authorized via PolicyKit, or passwordless `sudo` as a
  fallback)
- A desktop environment with a `StatusNotifierWatcher`/host: KDE Plasma works natively; GNOME
  needs the extension linked above; most other DEs (XFCE, LXQt, ...) support this natively too.
- (Optional) a kernel/firmware combination exposing `/sys/firmware/acpi/platform_profile` for the
  fan/cooling profile menu; not all hardware has this, and the app works fine without it.
- `gettext` and, optionally, `intltool` if you want translated strings installed (the app still
  works fine in English without them).

On Debian/Ubuntu:

```
sudo apt install python3-gi python3-dbus python3-psutil libcpufreq0 policykit-1 gettext
```

## Installing

```
sudo ./install.sh
```

This installs the Python package, both executables, tray icons, the desktop entry, the PolicyKit
action, the D-Bus system-service activation files, and (if `msgfmt` is available) translations —
everything needed system-wide. Re-run it any time after pulling changes to update an existing
install; if the app is already running, restart it afterwards:

```
killall indicator-cpufreq indicator-cpufreq-selector 2>/dev/null; indicator-cpufreq &
```

There's no need to log out/in unless you want the desktop entry to show up in a freshly-scanned
application menu.

### Alternative: patching an apt-installed copy

If you'd rather keep using a `indicator-cpufreq` package installed from a PPA/apt and just update
the two Python modules and the selector script in place:

1. `sudo apt-get install indicator-cpufreq`
2. Find the installed package directory (usually `/usr/lib/python3/dist-packages/indicator_cpufreq`)
   and overwrite `cpufreq.py` and `indicator.py` with the ones from this checkout.
3. Copy `bin/indicator-cpufreq-selector` to `/usr/bin/indicator-cpufreq-selector`.

This won't pick up the PolicyKit action or D-Bus service-activation changes made in this fork, so
`install.sh` is the recommended route.

## Running

```
indicator-cpufreq            # run the tray indicator (as the normal user)
indicator-cpufreq -f         # also show frequency as text next to the icon
indicator-cpufreq -v|-vv|-d  # increase log verbosity (warning/info/debug)
```

The privileged helper (`indicator-cpufreq-selector`) doesn't need to be started manually — it's
activated on demand over the system D-Bus the first time you change a frequency, governor, or
core's online state, and runs as root per `data/com.ubuntu.IndicatorCpufreqSelector.service`.

## Uninstalling

Remove the files `install.sh` put in place:

```
sudo rm -rf /usr/local/lib/python3*/dist-packages/indicator_cpufreq
sudo rm -f /usr/bin/indicator-cpufreq /usr/bin/indicator-cpufreq-selector
sudo rm -f /usr/share/applications/indicator-cpufreq.desktop
sudo rm -f /usr/share/polkit-1/actions/com.ubuntu.indicatorcpufreq.policy
sudo rm -f /usr/share/dbus-1/system-services/com.ubuntu.IndicatorCpufreqSelector.service
sudo rm -f /etc/dbus-1/system.d/com.ubuntu.IndicatorCpufreqSelector.conf
sudo rm -f /usr/share/icons/{ubuntu-mono-dark,ubuntu-mono-light}/status/22/indicator-cpufreq*
sudo rm -f /usr/share/icons/hicolor/22x22/status/indicator-cpufreq*
sudo rm -f /usr/share/locale/*/LC_MESSAGES/indicator-cpufreq.mo
```

## License

GPL-3 (see `COPYING`). Originally by Artem Popov, imported from
https://launchpad.net/indicator-cpufreq.
