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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import AppIndicator3 as appindicator

import locale
import dbus

from indicator_cpufreq import cpufreq

import gettext
from gettext import gettext as _
#gettext.textdomain('indicator-cpufreq')

def readable_frequency(f):
    # temp hack for properly displaying intel turbo mode (actual freq + 1000kHz)
    label = _("%s GHz") % locale.format(_("%.2f"), f / 1.0e6)
    if f % 10000 != 0:
        label = label + " " + _("(turbo mode)")
    return label

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

class MyIndicator(object):
    def __init__(self, show_frequency=False):
        self.show_frequency = show_frequency
        self.ind = appindicator.Indicator.new("indicator-cpufreq",
            "indicator-cpufreq",
            appindicator.IndicatorCategory.HARDWARE)
        self.ind.set_status(appindicator.IndicatorStatus.ACTIVE)

        self.ind.set_icon_theme_path("/usr/share/icons")
        #self.set_icon(get_data_file('media', 'indicator-cpufreq.png'))
        self.ind.set_icon('indicator-cpufreq')
        
        menu = Gtk.Menu()
        self.select_items = {}
        group = []
        
        maxcpu = 0
        while cpufreq.cpu_exists(maxcpu) == 0:
            maxcpu += 1
        self.cpus = range(maxcpu)
        
        # frequency menu items
        #freqs = cpufreq.get_available_frequencies(self.cpus[0])
        freqs = reversed(sorted(set(cpufreq.get_available_frequencies(self.cpus[0]))))
        for freq in freqs:
            menu_item = Gtk.RadioMenuItem.new_with_label(group, readable_frequency(freq))
            group = menu_item.get_group()
            menu.append(menu_item)
            menu_item.connect("activate", self.select_activated, 'frequency', freq)
            self.select_items[freq] = menu_item

        menu.append(Gtk.SeparatorMenuItem())

        # governor menu items
        governors = cpufreq.get_available_governors(self.cpus[0])
        for governor in governors:
            if governor == 'userspace':
                continue
            menu_item = Gtk.RadioMenuItem.new_with_label(group, readable_governor(governor))
            group = menu_item.get_group()
            menu.append(menu_item)
            menu_item.connect('activate', self.select_activated, 'governor', governor)
            self.select_items[governor] = menu_item

        menu.show_all()        
        self.ind.set_menu(menu)
        self.update_ui()
        GLib.timeout_add_seconds(1, self.poll_timeout)
    
    def poll_timeout(self):
        self.update_ui()
        return True

    def update_ui(self):
        for i in self.select_items.values():
            i.handler_block_by_func(self.select_activated)
        
        fmin, fmax, governor = cpufreq.get_policy(self.cpus[0])
        # use the highest freq among cores for display
        freq = max([cpufreq.get_freq_kernel(cpu) for cpu in self.cpus])
        
        ratio = min([25, 50, 75, 100], key=lambda x: abs((fmax - fmin) * x / 100.0 - (freq - fmin)))
        if freq < fmax and ratio == 100:
            ratio = 75
        
        #self.set_icon(get_data_file('media', 'indicator-cpufreq-%d.png' % ratio))
        self.ind.set_icon('indicator-cpufreq-%d' % ratio)
        if self.show_frequency:
            self.ind.set_label(readable_frequency(freq), "3.00 GHz")
        if governor == 'userspace':
            self.select_items[freq].set_active(True)
        else:
            self.select_items[governor].set_active(True)
        
        for i in self.select_items.values():
            i.handler_unblock_by_func(self.select_activated)
       
        #self.props.label = readable_frequency(freq)
    
    def select_activated(self, menuitem, select, value):
        if menuitem.get_active():
            bus = dbus.SystemBus()
            proxy = bus.get_object("com.ubuntu.IndicatorCpufreqSelector", "/Selector", introspect=False)
            cpus = [dbus.UInt32(cpu) for cpu in self.cpus]
            if select == 'frequency':
                proxy.SetFrequency(cpus, dbus.UInt32(value),
                    dbus_interface='com.ubuntu.IndicatorCpufreqSelector')
            else:
                proxy.SetGovernor(cpus, value,
                    dbus_interface='com.ubuntu.IndicatorCpufreqSelector')
    
    def can_set(self):
        pass

if __name__ == "__main__":
    ind = MyIndicator()
    Gtk.main()

