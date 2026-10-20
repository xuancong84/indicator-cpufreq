# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

# Vendor fan control: fan profile (cooling mode) selection and fixed fan
# speed. Every capability is optional; callers must check has_fan_profile()/
# has_fan_speed() first, and show nothing for what isn't detected.
#
# Supported backend: the out-of-tree Gigabyte AERO/AORUS WMI driver
# (github.com/tangalbert919/gigabyte-laptop-wmi, module aorus_laptop),
# /sys/devices/platform/aorus_laptop/{fan_mode,fan_custom_speed}.
#
# Set INDICATOR_CPUFREQ_SYSFS_ROOT to a directory mirroring /sys to test
# against a fake sysfs tree.

import glob
import os

SYSFS_ROOT = os.environ.get('INDICATOR_CPUFREQ_SYSFS_ROOT', '/sys')

AORUS_PATH = os.path.join(SYSFS_ROOT, 'devices/platform/aorus_laptop')

# fan_mode values. 3 (plain "custom", without auto curve or fixed speed) is
# deliberately not offered.
AORUS_PROFILES = [
	('normal', 0),
	('silent', 1),
	('gaming', 2),
	('auto', 4),	# custom mode following the EC's 15-point fan curve
	('fixed', 5),	# custom mode at fan_custom_speed
]
AORUS_FIXED_MODE = 5

# Fixed speed is exposed in percent. The minimum is kept at 25% for both
# driver generations: that's the lowest the original driver accepts, and
# the newer one would otherwise allow stopping the fans entirely.
FAN_SPEED_MIN = 25
FAN_SPEED_MAX = 100

def _read(path):
	try:
		with open(path) as fp:
			return fp.read().strip()
	except OSError:
		return None

def _write(path, value):
	try:
		with open(path, 'w') as fp:
			print(value, file=fp, flush=True)
		return 0
	except OSError:
		return -1

def _aorus_attr(name):
	return os.path.join(AORUS_PATH, name)

def _aorus_raw_speed():
	# Driver 0.1.x takes fan_custom_speed as a percentage (25..100 in steps
	# of 5) and maps it to the EC's 0-255 duty itself; newer upstream
	# versions take the raw 0-255 duty and also add a fan_pwm attribute,
	# which is how they're told apart (MODULE_VERSION is "0.01" in both).
	return os.path.exists(_aorus_attr('fan_pwm'))

def _has_aorus():
	return os.path.isfile(_aorus_attr('fan_mode'))

# --- fan profile -----------------------------------------------------------

def has_fan_profile():
	return _has_aorus()

def get_fan_profile_choices():
	if _has_aorus():
		return [name for name, mode in AORUS_PROFILES]
	return []

def get_fan_profile():
	# Note: the aorus driver reports the last mode written through it (it
	# only reads the real EC state once, at module load), so changes made
	# behind its back aren't reflected here.
	if _has_aorus():
		value = _read(_aorus_attr('fan_mode'))
		for name, mode in AORUS_PROFILES:
			if value == str(mode):
				return name
	return None

def set_fan_profile(profile):
	if _has_aorus():
		for name, mode in AORUS_PROFILES:
			if name == profile:
				return _write(_aorus_attr('fan_mode'), mode)
	return -1

# --- fixed fan speed -------------------------------------------------------

def has_fan_speed():
	return _has_aorus() and os.path.isfile(_aorus_attr('fan_custom_speed'))

def get_fan_speed_range():
	"""(min, max, step) in percent."""
	return (FAN_SPEED_MIN, FAN_SPEED_MAX, 1 if _aorus_raw_speed() else 5)

def snap_fan_speed(percent):
	fmin, fmax, step = get_fan_speed_range()
	percent = max(fmin, min(fmax, percent))
	return int(round(percent / step) * step)

def get_fan_speed():
	value = _read(_aorus_attr('fan_custom_speed'))
	try:
		value = int(value)
	except (TypeError, ValueError):
		return None
	if _aorus_raw_speed():
		return int(round(value * 100 / 255))
	return value

def set_fan_speed(percent):
	"""Set a fixed fan speed, switching to fixed mode if not already in it."""
	if not has_fan_speed():
		return -1
	percent = snap_fan_speed(percent)
	value = int(round(percent * 255 / 100)) if _aorus_raw_speed() else percent
	if _write(_aorus_attr('fan_custom_speed'), value):
		return -1
	if _read(_aorus_attr('fan_mode')) != str(AORUS_FIXED_MODE):
		return _write(_aorus_attr('fan_mode'), AORUS_FIXED_MODE)
	return 0

# --- readings --------------------------------------------------------------

def get_fan_rpm_paths():
	"""fan*_input files of the detected fan driver's hwmon device."""
	if not _has_aorus():
		return []
	return sorted(glob.glob(os.path.join(AORUS_PATH, 'hwmon/hwmon*/fan*_input')))

def get_fan_rpm(path):
	try:
		return int(_read(path))
	except (TypeError, ValueError):
		return None
