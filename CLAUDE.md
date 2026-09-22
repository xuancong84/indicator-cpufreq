# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Ubuntu/Unity AppIndicator applet (ported from GNOME's CPU frequency applet) that shows current
CPU frequency in the system tray and lets the user switch CPU frequency/governor. Python 3 + GTK3
+ AppIndicator3, packaged with `distutils-extra`. No test suite, linter config, or CI exists in
this repo — there is nothing to run beyond the app itself.

## Running / installing

There's no build step; it's plain Python invoked from `bin/`:

```
./bin/indicator-cpufreq            # run the tray indicator (as the normal user)
./bin/indicator-cpufreq -f         # also show frequency as text next to the icon
./bin/indicator-cpufreq -v|-vv|-d  # increase log verbosity (warning/info/debug)
sudo ./bin/indicator-cpufreq-selector   # run the privileged D-Bus backend manually (for testing)
```

`bin/indicator-cpufreq` adds the repo root to `sys.path` when run from a checkout/symlink, so it
imports the local `indicator_cpufreq` package without installing anything.

Packaging is via `setup.py` (`DistUtilsExtra.auto.setup`), which also installs the tray icons from
`icons/ubuntu-mono-{dark,light}` as `data_files`. There's no `pip install -e` workflow — see
README.md for the manual "overwrite the installed .py files" update procedure used on real Ubuntu
installs.

## Architecture: two processes split by privilege

The app is deliberately split into an **unprivileged UI process** and a **privileged D-Bus
service**, because changing CPU frequency/governor requires root:

- `bin/indicator-cpufreq` → `indicator_cpufreq/indicator.py` (`MyIndicator`): runs as the desktop
  user. Builds the AppIndicator3 tray menu (frequency choices + governor choices as radio items),
  polls hardware state once a second (`GLib.timeout_add_seconds(1, self.poll_timeout)`), and
  updates the icon/label/radio selection accordingly. It never touches hardware directly to make
  changes — on menu activation (`select_activated`) it calls out over the **system** D-Bus to
  `com.ubuntu.IndicatorCpufreqSelector`.
- `bin/indicator-cpufreq-selector` (`IndicatorCpufreqSelector`, self-contained script, not part of
  the `indicator_cpufreq` package): a D-Bus system-bus service, activated on demand per
  `data/com.ubuntu.IndicatorCpufreqSelector.service` (`User=root`). Exposes `SetFrequency` and
  `SetGovernor` D-Bus methods that actually write hardware policy via `indicator_cpufreq.cpufreq`.

Authorization for the privileged calls is layered, in `_check_polkit_privilege`:
1. If called locally (no D-Bus sender/conn), always allowed.
2. Look up the calling PID's user via `psutil` + `sudo -l -U <user>`; passwordless sudoers
   (`NOPASSWD:ALL`) are allowed outright, and non-sudoers (missing `(ALL:ALL)ALL`) are rejected
   immediately with `PermissionDeniedByPolicy`.
3. Otherwise, fall through to PolicyKit (`org.freedesktop.PolicyKit1`), checked against the action
   ID declared in `indicator_cpufreq/com.ubuntu.indicatorcpufreq.policy.in`
   (`com.ubuntu.indicatorcpufreqselector.setfrequencyscaling`).

`data/com.ubuntu.IndicatorCpufreqSelector.conf` is the D-Bus bus policy that allows the service to
be owned by root and its methods invoked by any user (the actual authorization happens in step 2/3
above, not at the bus level). When the frontend gets a `PermissionDeniedByPolicy` D-Bus exception,
it shows a GTK error dialog (`show_gtk_dialog` in `indicator.py`) instead of crashing.

## `cpufreq.py`: dual backend, chosen at import time

`indicator_cpufreq/cpufreq.py` wraps `libcpufreq` via `ctypes` (struct defs + `argtypes`/`restype`
declarations for every `cpufreq_*` function, e.g. `get_policy`, `get_available_frequencies`,
`set_frequency`, `modify_policy_governor`). This works on systems using the classic `acpi-cpufreq`
driver family.

On systems using `intel_pstate` (increasingly the default), `libcpufreq` reports no available
frequencies. The module detects this **once at import time**:

```python
if not get_available_frequencies(0):
    get_available_frequencies = get_available_frequencies2
    set_frequency = set_frequency2
    modify_policy_governor = modify_policy_governor2
    get_freq_hardware = get_freq_kernel = get_frequency
```

The `*2` fallback functions read/write directly under
`/sys/devices/system/cpu/cpu{N}/cpufreq/` (`scaling_max_freq`, `scaling_governor`) and synthesize
an available-frequency list as 100 MHz steps between hardware min/max
(`get_available_frequencies2`) since sysfs doesn't expose a discrete list for `intel_pstate`. When
modifying this file, remember that whichever backend is picked applies process-wide for the
lifetime of both the indicator process and the selector process — there's no per-call backend
switching.

## i18n

User-facing strings go through `gettext` (`_()`), textdomain `indicator-cpufreq`. Translated
catalogs live in `po/*.po`, template in `po/indicator-cpufreq.pot`. `governor_names` in
`indicator.py` maps raw kernel governor names (`ondemand`, `performance`, etc.) to translated
display labels — add new governors there if the kernel exposes more.
