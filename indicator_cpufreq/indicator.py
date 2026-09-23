# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Copyright (C) 2010 Artem Popov <artfwo@gmail.com>
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

# FIXME:
# org.freedesktop.PolicyKit1 (cheat at distutils-extra)
import os, sys, math

# Native Wayland forbids clients from positioning their own top-level windows
# or hiding them from the taskbar (no equivalent of X11's WM_NORMAL_HINTS
# position or _NET_WM_STATE_SKIP_TASKBAR). Since this app pops up menus at
# arbitrary screen coordinates via an invisible anchor window and needs that
# window to stay out of the taskbar, run it through XWayland instead, where
# both of those still work.
os.environ.setdefault('GDK_BACKEND', 'x11')

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
import dbus
import dbus.service
import dbus.mainloop.glib

from indicator_cpufreq import cpufreq

import gettext
from gettext import gettext as _
#gettext.textdomain('indicator-cpufreq')

def readable_frequency(f):
	# temp hack for properly displaying intel turbo mode (actual freq + 1000kHz)
	label = "%.2f GHz" % (f / 1.0e6)
	if f % 10000 != 0:
		label = label + " " + _("(turbo mode)")
	return label

def readable_frequency_range(fmin, fmax):
	return "%.2f–%.2f GHz" % (fmin / 1.0e6, fmax / 1.0e6)

# Rough GTK menu item height and vertical margin to leave for panels/
# decorations, used only to estimate how many grid rows fit on screen.
MENU_ITEM_HEIGHT_PX = 28
MENU_RESERVED_HEIGHT_PX = 150

governor_names = {
	'conservative': _("Conservative"),
	'ondemand': _("Ondemand"),
	#'userspace': _("Userspace"),
	'powersave': _("Powersave"),
	'performance': _("Performance"),
}

def readable_governor(g):
	if g in governor_names:
		return governor_names[g]
	else:
		return g

platform_profile_names = {
	'low-power': _("Low power"),
	'cool': _("Cool"),
	'quiet': _("Quiet"),
	'balanced': _("Balanced"),
	'balanced-performance': _("Balanced performance"),
	'performance': _("Performance"),
	'custom': _("Custom"),
}

def readable_platform_profile(p):
	return platform_profile_names.get(p, p)

def show_gtk_dialog(message, title="Permission denied"):
    dialog = Gtk.MessageDialog(
        transient_for=None,
        flags=0,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=title,
    )
    dialog.format_secondary_text(message)
    dialog.set_modal(True)
    dialog.set_keep_above(True)
    dialog.connect("response", lambda d, r: d.destroy())
    dialog.show_all()

class StatusNotifierItem(dbus.service.Object):
	"""Hand-rolled org.kde.StatusNotifierItem service.

	AppIndicator3/libdbusmenu always collapses left- and right-click into the
	same 'Menu' popup. By not exposing a Menu property at all, hosts fall back
	to calling Activate() (left-click) and ContextMenu() (right-click)
	separately, which lets us show two different menus.
	"""

	IFACE = 'org.kde.StatusNotifierItem'
	PATH = '/StatusNotifierItem'

	def __init__(self, bus, on_activate, on_context_menu):
		dbus.service.Object.__init__(self, bus, self.PATH)
		self._on_activate = on_activate
		self._on_context_menu = on_context_menu
		self.icon_name = 'indicator-cpufreq'
		self.title = _("CPU Frequency Scaling Indicator")
		self.tooltip_text = ''

	@dbus.service.method(dbus_interface=IFACE, in_signature='ii', out_signature='')
	def Activate(self, x, y):
		self._on_activate(x, y)

	@dbus.service.method(dbus_interface=IFACE, in_signature='ii', out_signature='')
	def SecondaryActivate(self, x, y):
		pass

	@dbus.service.method(dbus_interface=IFACE, in_signature='ii', out_signature='')
	def ContextMenu(self, x, y):
		self._on_context_menu(x, y)

	@dbus.service.method(dbus_interface=IFACE, in_signature='is', out_signature='')
	def Scroll(self, delta, orientation):
		pass

	@dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
	def GetAll(self, interface_name):
		if interface_name != self.IFACE:
			return dbus.Dictionary({}, signature='sv')
		return dbus.Dictionary({
			'Category': 'Hardware',
			'Id': 'indicator-cpufreq',
			'Title': self.title,
			'Status': 'Active',
			'WindowId': dbus.UInt32(0),
			'IconThemePath': '/usr/share/icons',
			'IconName': self.icon_name,
			'OverlayIconName': '',
			'AttentionIconName': '',
			'ItemIsMenu': False,
			'ToolTip': (self.icon_name, dbus.Array([], signature='(iiay)'), self.title, self.tooltip_text),
		}, signature='sv')

	@dbus.service.method(dbus_interface=dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
	def Get(self, interface_name, property_name):
		return self.GetAll(interface_name)[property_name]

	@dbus.service.signal(dbus_interface=IFACE)
	def NewIcon(self):
		pass

	@dbus.service.signal(dbus_interface=IFACE)
	def NewTitle(self):
		pass

	@dbus.service.signal(dbus_interface=IFACE)
	def NewToolTip(self):
		pass

	def set_icon(self, icon_name):
		if icon_name != self.icon_name:
			self.icon_name = icon_name
			self.NewIcon()

	def set_tooltip(self, title, text):
		if (title, text) != (self.title, self.tooltip_text):
			self.title = title
			self.tooltip_text = text
			self.NewTitle()
			self.NewToolTip()

class MyIndicator(object):
	def __init__(self, show_frequency=False):
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

		self.show_frequency = show_frequency
		self.session_bus = dbus.SessionBus()

		self.cpus = list(range(cpufreq.get_maxcpu()))

		# group cores by their hardware frequency range (e.g. P-cores vs
		# E-cores). Computed once: cpuinfo_min/max_freq is a fixed hardware
		# property. A core that's offline reports (0, 0) for its limits (its
		# cpufreq files exist but reading them returns EBUSY), which would
		# wrongly lump every already-disabled core into one bogus group, so
		# any that start offline are briefly brought online to read their
		# real limits, then restored to offline.
		offline_cpus = [cpu for cpu in self.cpus if not cpufreq.get_cpu_online(cpu)]
		if offline_cpus:
			try:
				self._set_cpus_online(offline_cpus, True)
			except dbus.DBusException as e:
				sys.stderr.write("Warning: could not probe offline CPUs for grouping: %s\n" % e)
				offline_cpus = []

		self.cpu_groups = {}
		for cpu in self.cpus:
			limits = cpufreq.get_hardware_limits(cpu)
			self.cpu_groups.setdefault(limits, []).append(cpu)

		if offline_cpus:
			self._set_cpus_online(offline_cpus, False)

		self.select_items = {}
		self.profile_items = {}
		self.freq_menu = self._build_freq_menu()
		self._core_menu = None

		# GTK needs a real, realized GdkWindow to anchor a popup menu to.
		# Since this app is triggered purely over D-Bus (Activate/ContextMenu)
		# and never otherwise creates a window, we keep one tiny invisible
		# window alive for the menus to popup against.
		self._anchor_win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
		self._anchor_win.set_type_hint(Gdk.WindowTypeHint.UTILITY)
		self._anchor_win.set_default_size(1, 1)
		self._anchor_win.set_decorated(False)
		self._anchor_win.set_skip_taskbar_hint(True)
		self._anchor_win.set_skip_pager_hint(True)
		self._anchor_win.set_opacity(0)
		self._anchor_win.move(0, 0)
		self._anchor_win.show()

		self.sni = StatusNotifierItem(self.session_bus,
			on_activate=self._show_freq_menu,
			on_context_menu=self._show_core_menu)

		try:
			watcher = self.session_bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
			dbus.Interface(watcher, 'org.kde.StatusNotifierWatcher').RegisterStatusNotifierItem(
				self.session_bus.get_unique_name())
		except dbus.DBusException as e:
			sys.stderr.write("Warning: failed to register with StatusNotifierWatcher: %s\n" % e)

		self.update_ui()
		GLib.timeout_add_seconds(1, self.poll_timeout)

	def _max_menu_rows(self):
		screen = Gdk.Screen.get_default()
		screen_height = screen.get_height() if screen else 1080
		return max(1, (screen_height - MENU_RESERVED_HEIGHT_PX) // MENU_ITEM_HEIGHT_PX)

	def _build_freq_menu(self):
		menu = Gtk.Menu()
		group = []

		freqs = list(reversed(sorted(set(cpufreq.get_available_frequencies2(self.cpus[0])))))
		columns = max(1, math.ceil(len(freqs) / self._max_menu_rows()))
		row = 0
		for i, freq in enumerate(freqs):
			menu_item = Gtk.RadioMenuItem.new_with_label(group, readable_frequency(freq))
			group = menu_item.get_group()
			col = i % columns
			menu.attach(menu_item, col, col + 1, row, row + 1)
			if col == columns - 1:
				row += 1
			menu_item.connect("activate", self.select_activated, 'frequency', freq)
			self.select_items[freq] = menu_item
		if len(freqs) % columns != 0:
			row += 1

		menu.attach(Gtk.SeparatorMenuItem(), 0, columns, row, row + 1)
		row += 1

		group = []
		governors = cpufreq.get_available_governors(self.cpus[0])
		col = 0
		for governor in governors:
			if governor == 'userspace':
				continue
			menu_item = Gtk.RadioMenuItem.new_with_label(group, readable_governor(governor))
			group = menu_item.get_group()
			menu.attach(menu_item, col, col + 1, row, row + 1)
			col += 1
			menu_item.connect('activate', self.select_activated, 'governor', governor)
			self.select_items[governor] = menu_item
		row += 1

		if cpufreq.has_platform_profile():
			profiles = cpufreq.get_platform_profile_choices()
			if profiles:
				menu.attach(Gtk.SeparatorMenuItem(), 0, columns, row, row + 1)
				row += 1
				# A real Gtk.MenuItem (GtkMenu's grid layout doesn't reliably
				# size/render non-GtkMenuItem children) kept sensitive, so the
				# text isn't drawn in the greyed-out "insensitive" style, but
				# with its clicks swallowed so it neither closes the menu nor
				# does anything when clicked.
				label_item = Gtk.MenuItem()
				label = Gtk.Label()
				label.set_markup("<b>%s</b>" % GLib.markup_escape_text(_("Fan:")))
				label.set_xalign(0)
				label_item.add(label)
				label_item.set_can_focus(False)
				label_item.connect("button-press-event", lambda w, e: True)
				label_item.connect("button-release-event", lambda w, e: True)
				menu.attach(label_item, 0, 1, row, row + 1)
				group = []
				col = 1
				for profile in profiles:
					if col >= columns:
						row += 1
						col = 0
					menu_item = Gtk.RadioMenuItem.new_with_label(group, readable_platform_profile(profile))
					group = menu_item.get_group()
					menu.attach(menu_item, col, col + 1, row, row + 1)
					col += 1
					menu_item.connect('activate', self.select_activated, 'platform_profile', profile)
					self.profile_items[profile] = menu_item

		menu.show_all()
		return menu

	def _build_core_menu(self):
		menu = Gtk.Menu()

		for (fmin, fmax), cpus in sorted(self.cpu_groups.items()):
			online = {cpu: cpufreq.get_cpu_online(cpu) for cpu in cpus}
			disableable = [cpu for cpu in cpus if cpufreq.get_cpu_online_path(cpu)]

			group_item = Gtk.CheckMenuItem.new_with_label(
				"%s: CPU%s" % (readable_frequency_range(fmin, fmax), "/".join(str(c) for c in cpus)))
			group_item.set_active(bool(disableable) and all(online[cpu] for cpu in disableable))
			group_item.set_sensitive(bool(disableable))
			self._keep_menu_open_on_click(group_item)
			menu.append(group_item)

			child_items = {}
			for cpu in cpus:
				item = Gtk.CheckMenuItem.new_with_label("    " + _("CPU %d") % cpu)
				item.set_active(online[cpu])
				item.set_sensitive(cpu in disableable)
				item.connect("toggled", self._core_toggled, cpu)
				self._keep_menu_open_on_click(item)
				menu.append(item)
				child_items[cpu] = item

			def on_group_toggled(gi, cpus=cpus, child_items=child_items):
				want_online = gi.get_active()
				for cpu in cpus:
					item = child_items[cpu]
					if item.get_sensitive() and item.get_active() != want_online:
						item.set_active(want_online)
			group_item.connect("toggled", on_group_toggled)

		menu.append(Gtk.SeparatorMenuItem())
		close_item = Gtk.MenuItem.new_with_label(_("Close"))
		menu.append(close_item)

		menu.show_all()
		return menu

	def _keep_menu_open_on_click(self, item):
		# Clicking any menu item, checkbox or not, normally closes the whole
		# menu (GtkMenuShell's default button-release handling deactivates
		# it). Intercepting the event here and returning True stops that
		# default handler from ever running, so multiple boxes can be
		# checked/unchecked in one go; we toggle the box ourselves instead,
		# which still fires its normal "toggled" handler.
		def on_button_release(widget, event):
			if widget.get_sensitive():
				widget.set_active(not widget.get_active())
			return True
		item.connect("button-release-event", on_button_release)

	def _set_cpus_online(self, cpus, online):
		bus = dbus.SystemBus()
		proxy = bus.get_object("com.ubuntu.IndicatorCpufreqSelector", "/Selector", introspect=False)
		proxy.SetCpuOnline([dbus.UInt32(cpu) for cpu in cpus], online,
			dbus_interface='com.ubuntu.IndicatorCpufreqSelector')

	def _core_toggled(self, item, cpu):
		want_online = item.get_active()
		try:
			self._set_cpus_online([cpu], want_online)
		except dbus.DBusException as e:
			name = e.get_dbus_name()
			msg = str(e)
			item.handler_block_by_func(self._core_toggled)
			item.set_active(not want_online)
			item.handler_unblock_by_func(self._core_toggled)
			if name == 'com.ubuntu.DeviceDriver.PermissionDeniedByPolicy':
				show_gtk_dialog(msg)

	def _popup(self, menu, x, y):
		self._anchor_win.move(x, y)
		self._anchor_win.present_with_time(Gdk.CURRENT_TIME)
		menu.popup_at_widget(self._anchor_win, Gdk.Gravity.NORTH_WEST, Gdk.Gravity.SOUTH_WEST, None)

	def _show_freq_menu(self, x, y):
		self._popup(self.freq_menu, x, y)

	def _show_core_menu(self, x, y):
		self._core_menu = self._build_core_menu()
		self._popup(self._core_menu, x, y)

	def poll_timeout(self):
		self.update_ui()
		return True

	def update_ui(self):
		for i in self.select_items.values():
			i.handler_block_by_func(self.select_activated)
		for i in self.profile_items.values():
			i.handler_block_by_func(self.select_activated)

		fmin, fmax, governor = cpufreq.get_policy(self.cpus[0])
		# use the highest freq among online cores for display
		freq = max([cpufreq.get_freq_kernel(cpu) for cpu in self.cpus if cpufreq.get_cpu_online(cpu)])

		# Scale the icon against the CPU's fixed hardware frequency range
		# (cpuinfo_min/max), not the policy window from get_policy() above
		# (scaling_min/max): on intel_pstate/amd-pstate drivers that window
		# itself tracks the live/EPP-driven frequency and can be only a few
		# hundred MHz wide even while actively adjusting, which pins the
		# icon near one end almost all the time regardless of how fast the
		# CPU is really running relative to what it's capable of.
		hw_min, hw_max = cpufreq.get_hardware_limits(self.cpus[0])
		# Equal-width 20% bands (0-20/20-40/.../80-100), not "nearest of the 5
		# anchor points" -- the latter makes the top band only the top 12.5%
		# of the range (the midpoint between the 75 and 100 anchors), which
		# on a CPU whose hardware max is a rarely-sustained turbo/boost peak
		# meant the icon could almost never show as full.
		pct = 0.0
		if hw_max > hw_min:
			pct = max(0.0, min(100.0, (freq - hw_min) * 100.0 / (hw_max - hw_min)))
		ratio = min(4, int(pct // 20)) * 25

		self.sni.set_icon('indicator-cpufreq-%d' % ratio)
		if self.show_frequency:
			self.sni.set_tooltip(readable_frequency(freq), readable_governor(governor))
		try:
			self.select_items[freq].set_active(True)
		except:
			pass
		try:
			self.select_items[governor].set_active(True)
		except:
			pass

		if self.profile_items:
			try:
				self.profile_items[cpufreq.get_platform_profile()].set_active(True)
			except:
				pass

		for i in self.select_items.values():
			i.handler_unblock_by_func(self.select_activated)
		for i in self.profile_items.values():
			i.handler_unblock_by_func(self.select_activated)

	def select_activated(self, menuitem, select, value):
		if menuitem.get_active():
			bus = dbus.SystemBus()
			proxy = bus.get_object("com.ubuntu.IndicatorCpufreqSelector", "/Selector", introspect=False)
			cpus = [dbus.UInt32(cpu) for cpu in self.cpus]
			try:
				if select == 'frequency':
					proxy.SetFrequency(cpus, dbus.UInt32(value),
						dbus_interface='com.ubuntu.IndicatorCpufreqSelector')
				elif select == 'governor':
					proxy.SetGovernor(cpus, value,
						dbus_interface='com.ubuntu.IndicatorCpufreqSelector')
				else:
					proxy.SetPlatformProfile(value,
						dbus_interface='com.ubuntu.IndicatorCpufreqSelector')
			except dbus.DBusException as e:
				name = e.get_dbus_name()
				msg = str(e)
				if name == 'com.ubuntu.DeviceDriver.PermissionDeniedByPolicy':
					show_gtk_dialog(msg)

if __name__ == "__main__":
	ind = MyIndicator()
	Gtk.main()
