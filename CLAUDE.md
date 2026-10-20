# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Linux system-tray applet (originally a Ubuntu/Unity port of GNOME's CPU frequency applet) that
shows current CPU frequency and lets the user change the max frequency / scaling governor, enable
or disable individual CPU cores, switch the ACPI platform profile, and (on supported vendor
drivers) pick a fan profile / fixed fan speed. Python 3 + GTK3 (PyGObject) + `dbus-python`. Works
with `acpi-cpufreq` as well as `intel_pstate`/`amd-pstate`, on KDE Plasma (X11/Wayland) natively
and GNOME via the AppIndicator/KStatusNotifierItem extension. No test suite, linter config, or CI
exists in this repo — there is nothing to run beyond the app itself.

## Running / installing

There's no build step; it's plain Python invoked from `bin/`:

```
./bin/indicator-cpufreq            # run the tray indicator (as the normal user)
./bin/indicator-cpufreq -f         # also put frequency/governor in the tray tooltip/title
./bin/indicator-cpufreq -v|-vv|-d  # increase log verbosity (warning/info/debug)
./bin/indicator-cpufreq --allow-multiple-instances   # skip the one-instance-per-user check
sudo ./bin/indicator-cpufreq-selector   # run the privileged D-Bus backend manually (for testing)
```

Both `bin/` scripts add the repo root to `sys.path` when run from a checkout/symlink, so they import
the local `indicator_cpufreq` package without installing anything. Note that the frontend talks to
whatever selector D-Bus activation starts (`/usr/bin/indicator-cpufreq-selector`), so to test
selector changes from a checkout either reinstall or kill the installed one and start the checkout's
copy with `sudo` before using the menu.

Installing system-wide is done with `sudo ./install.sh` (Python package into site-packages, both
executables to `/usr/bin`, icons, desktop entry, PolicyKit policy, D-Bus service + bus-policy files,
translations; then reloads dbus). Re-run it after changes and restart the app
(`killall indicator-cpufreq indicator-cpufreq-selector`). `setup.py` (`DistUtilsExtra.auto.setup`)
still exists but does **not** install the `data/` D-Bus files — prefer `install.sh`.

## Architecture: two processes split by privilege

- `bin/indicator-cpufreq` → `indicator_cpufreq/indicator.py` (`MyIndicator`): runs as the desktop
  user, never writes hardware state itself.
- `bin/indicator-cpufreq-selector` (`IndicatorCpufreqSelector`, self-contained script, not part of
  the package): root D-Bus system-bus service at `com.ubuntu.IndicatorCpufreqSelector` `/Selector`,
  activated on demand per `data/com.ubuntu.IndicatorCpufreqSelector.service` (`User=root`). Methods:
  `SetFrequency(au,u)`, `SetGovernor(au,s)`, `SetCpuOnline(au,b)`, `SetPlatformProfile(s)` (calling
  `indicator_cpufreq.cpufreq`; their return codes are ignored, so failures are silent), and
  `SetFanProfile(s)`, `SetFanSpeed(u)` (calling `indicator_cpufreq.fan`; these validate the value
  against what `fan.py` detects and raise `...InvalidArgument` / `...Failed` D-Bus errors).

### Frontend (`indicator.py`)

- **Tray icon is a hand-rolled `org.kde.StatusNotifierItem`** (`StatusNotifierItem` class), not
  AppIndicator3. It deliberately exposes no `Menu` property, so hosts call `Activate` (left-click)
  and `ContextMenu` (right-click) separately, letting the two clicks show different menus. It
  registers with `org.kde.StatusNotifierWatcher` on the session bus. Icons are named
  `indicator-cpufreq-{0,25,50,75,100}` and looked up from the installed icon theme.
- **Single instance per user**: claims session-bus name `com.ubuntu.IndicatorCpufreq` with
  `do_not_queue`; exits if already owned (unless `--allow-multiple-instances`).
- **Menus are plain `Gtk.Menu`s popped up against a tiny invisible anchor window** (`_popup`),
  since the app has no other window.
  - Left-click → `_build_freq_menu` (built once at startup, laid out as a grid sized by
    `_max_menu_rows`): frequency radio items, governor radio items, and — only if
    `cpufreq.has_platform_profile()` — a "Power:" row of platform-profile radio items
    (`self.profile_items`, labels from `platform_profile_names`); then `_build_fan_section`: a
    "Fan:" profile row (`self.fan_profile_items`), a "Fan speed:" `Gtk.Scale` (`self.fan_scale`)
    and an RPM readout (`self.fan_rpm_label`), each only if `fan.py` detects it. The slider lives
    in a `Gtk.MenuItem` that forwards pointer events to it (`_make_slider_item`), since a menu
    item's input window otherwise swallows them and closes the menu; slider changes are debounced
    (400 ms) before calling `SetFanSpeed`.
  - Right-click → `_build_core_menu` (rebuilt on every open): per-core online checkboxes grouped by
    hardware freq range (`self.cpu_groups`, e.g. P-cores vs E-cores) with a group header toggle, plus
    an icon-mode radio (`'cap'` = configured max freq, `'live'` = current freq). Clicks keep the menu
    open via `_keep_menu_open_on_click`.
- **Polling**: `update_ui` runs every second (`GLib.timeout_add_seconds`) — sets icon level from
  20%-wide bands of the hardware (cpuinfo) min/max range, updates tooltip if `-f`, and re-checks the
  active governor and platform profile. It blocks `select_activated` handlers while doing so, so
  programmatic `set_active` doesn't fire D-Bus calls. The frequency radio is synced only once at
  startup (`_sync_freq_selection`) because `scaling_max_freq` drifts on pstate drivers.
- At startup, any offline cores are briefly brought online (via the selector) so their hardware
  limits can be read for grouping, then put back offline.
- Menu actions (`select_activated`, `_core_toggled`) call the selector over the **system** bus; a
  `com.ubuntu.DeviceDriver.PermissionDeniedByPolicy` error shows a GTK dialog (`show_gtk_dialog`).

### Backend (`bin/indicator-cpufreq-selector`)

Authorization, in `_check_polkit_privilege`:
1. If called locally (no D-Bus sender/conn), always allowed.
2. Look up the caller PID's user via `psutil` + `sudo -l -U <user>`; passwordless sudoers
   (`NOPASSWD:ALL`) are allowed outright, non-sudoers (missing `(ALL:ALL)ALL`) are rejected with
   `PermissionDeniedByPolicy`.
3. Otherwise PolicyKit `CheckAuthorization` with interactive auth, against the action IDs in
   `indicator_cpufreq/com.ubuntu.indicatorcpufreq.policy.in`:
   `...setfrequencyscaling` (frequency + governor), `...setcpuonline`, `...setplatformprofile`,
   `...setfan` (fan profile + speed), all prefixed `com.ubuntu.indicatorcpufreqselector.`. New
   privileged methods need a new action there.

`data/com.ubuntu.IndicatorCpufreqSelector.conf` is the bus policy letting root own the name and any
user call it; real authorization is the step above.

`SuspendGuard` holds a systemd-logind `delay` sleep inhibitor: on `PrepareForSleep(True)` it brings
all offline cores back online and releases the inhibitor; on resume it re-offlines them and re-arms.

## `cpufreq.py`: hardware access

**Frequency/governor — dual backend chosen at import time.** It wraps `libcpufreq` via `ctypes`
(struct defs + `argtypes`/`restype` for each `cpufreq_*` function). On `intel_pstate`/`amd-pstate`
libcpufreq reports no available frequencies, so at the bottom of the module:

```python
if not get_available_frequencies(0):
    get_available_frequencies = get_available_frequencies2
    set_frequency = set_frequency2
    modify_policy_governor = modify_policy_governor2
    get_freq_hardware = get_freq_kernel = get_frequency
```

The `*2` functions read/write `/sys/devices/system/cpu/cpu{N}/cpufreq/` (`scaling_max_freq`,
`scaling_governor`) directly and synthesize 100 MHz steps between hardware min/max. The chosen
backend applies process-wide for the lifetime of both processes — no per-call switching.

**Core online/offline** (`get_cpu_online_path`, `get_cpu_online`, `set_cpu_online`): sysfs
`/sys/devices/system/cpu/cpuN/online`. Cores without that file (typically CPU0) can't be disabled.
Offline cores report `(0, 0)` hardware limits.

**Platform profile ("Power:" row)**: `has_platform_profile`, `get_platform_profile_choices`,
`get_platform_profile`, `set_platform_profile` read/write the legacy aggregate interface
`/sys/firmware/acpi/platform_profile{,_choices}`; the firmware decides fan curves/power limits per
profile. Choices are read once when the left-click menu is built.

## `fan.py`: vendor fan control

Capabilities are detected independently (`has_fan_profile`, `has_fan_speed`, `get_fan_rpm_paths`)
and the menu shows nothing for what isn't detected. Generic hwmon `pwm*` control and fan-curve
editing are deliberately out of scope. The only backend so far is the out-of-tree Gigabyte
AERO/AORUS driver `aorus_laptop` (`/sys/devices/platform/aorus_laptop/`):
- `fan_mode`: 0 normal, 1 silent, 2 gaming, 3 custom (not offered), 4 auto (EC fan curve),
  5 fixed. Read-back is the driver's cached last-written value, not live EC state.
- `fan_custom_speed`: driver 0.1.x takes percent 25..100 in steps of 5; newer upstream takes raw
  0..255 and adds a `fan_pwm` attribute, which is how `_aorus_raw_speed()` tells them apart
  (MODULE_VERSION is "0.01" in both). `fan.py` always speaks percent, min 25%.
  `set_fan_speed` writes the speed then switches to fixed mode.
- RPMs from the device's own `hwmon/hwmon*/fan*_input`; channels that never read nonzero (absent
  fans) are hidden by the UI.

`INDICATOR_CPUFREQ_SYSFS_ROOT=<dir>` points `fan.py` at a fake sysfs tree for testing.

## i18n

User-facing strings go through `gettext` (`_()`), textdomain `indicator-cpufreq`. Catalogs in
`po/*.po`, template `po/indicator-cpufreq.pot`. `governor_names`, `platform_profile_names` and
`fan_profile_names` in `indicator.py` map raw kernel/driver names to translated labels — add new
ones there if more are exposed (unknown names are shown raw).
