# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
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
### END LICENSE

from ctypes import *
from ctypes.util import find_library

_libcpufreq = cdll.LoadLibrary(find_library("cpufreq"))

class _cpufreq_policy(Structure):
	_fields_ = [
		("min", c_ulong),
		("max", c_ulong),
		("governor", c_char_p)]

class _cpufreq_available_governors(Structure):
	pass
_cpufreq_available_governors._fields_ = [
	("governor", c_char_p),
	("next", POINTER(_cpufreq_available_governors)),
	("first", POINTER(_cpufreq_available_governors))]

class _cpufreq_available_frequencies(Structure):
	pass
_cpufreq_available_frequencies._fields_ = [
	("frequency", c_ulong),
	("next", POINTER(_cpufreq_available_frequencies)),
	("first", POINTER(_cpufreq_available_frequencies))]

class _cpufreq_affected_cpus(Structure):
	pass
_cpufreq_affected_cpus._fields_ = [
	("cpu", c_uint),
	("next", POINTER(_cpufreq_affected_cpus)),
	("first", POINTER(_cpufreq_affected_cpus))]

class _cpufreq_stats(Structure):
	pass
_cpufreq_stats._fields_ = [
	("frequency", c_ulong),
	("time_in_state", c_ulonglong),
	("next", POINTER(_cpufreq_stats)),
	("first", POINTER(_cpufreq_stats))]

###############################################################################

_libcpufreq.cpufreq_cpu_exists.argtypes = [c_uint]
_libcpufreq.cpufreq_cpu_exists.restype = c_int

_libcpufreq.cpufreq_get_freq_kernel.argtypes = [c_uint]
_libcpufreq.cpufreq_get_freq_kernel.restype = c_ulong

_libcpufreq.cpufreq_get_freq_hardware.argtypes = [c_uint]
_libcpufreq.cpufreq_get_freq_hardware.restype = c_ulong

_libcpufreq.cpufreq_get_transition_latency.argtypes = [c_uint]
_libcpufreq.cpufreq_get_transition_latency.restype = c_ulong

_libcpufreq.cpufreq_get_hardware_limits.argtypes = [c_uint, POINTER(c_ulong), POINTER(c_ulong)]
_libcpufreq.cpufreq_get_hardware_limits.restype = c_int

_libcpufreq.cpufreq_get_driver.argtypes = [c_uint]
_libcpufreq.cpufreq_get_driver.restype = c_char_p
#extern void   cpufreq_put_driver(char * ptr);

_libcpufreq.cpufreq_get_policy.argtypes = [c_uint]
_libcpufreq.cpufreq_get_policy.restype = POINTER(_cpufreq_policy)
#extern void cpufreq_put_policy(struct cpufreq_policy *policy);

_libcpufreq.cpufreq_get_available_governors.argtypes = [c_uint]
_libcpufreq.cpufreq_get_available_governors.restype = POINTER(_cpufreq_available_governors)
#extern void cpufreq_put_available_governors(struct _cpufreq_available_governors *first);

_libcpufreq.cpufreq_get_available_frequencies.argtypes = [c_uint]
_libcpufreq.cpufreq_get_available_frequencies.restype = POINTER(_cpufreq_available_frequencies)
#extern void cpufreq_put_available_frequencies(struct _cpufreq_available_frequencies *first);

_libcpufreq.cpufreq_get_affected_cpus.argtypes = [c_uint]
_libcpufreq.cpufreq_get_affected_cpus.restype = POINTER(_cpufreq_affected_cpus)
#extern void cpufreq_put_affected_cpus(struct _cpufreq_affected_cpus *first);

_libcpufreq.cpufreq_get_related_cpus.argtypes = [c_uint]
_libcpufreq.cpufreq_get_related_cpus.restype = POINTER(_cpufreq_affected_cpus)
#extern void cpufreq_put_related_cpus(struct _cpufreq_affected_cpus *first);

_libcpufreq.cpufreq_get_stats.argtypes = [c_uint, POINTER(c_ulonglong)]
_libcpufreq.cpufreq_get_stats.restype = POINTER(_cpufreq_stats)
#extern void cpufreq_put_stats(struct _cpufreq_stats *stats);

_libcpufreq.cpufreq_get_transitions.argtypes = [c_uint]
_libcpufreq.cpufreq_get_transitions.restype = c_ulong

_libcpufreq.cpufreq_set_policy.argtypes = [c_uint, POINTER(_cpufreq_policy)]
_libcpufreq.cpufreq_set_policy.restype = c_int

_libcpufreq.cpufreq_modify_policy_min.argtypes = [c_uint, c_ulong]
_libcpufreq.cpufreq_modify_policy_min.restype = c_int

_libcpufreq.cpufreq_modify_policy_max.argtypes = [c_uint, c_ulong]
_libcpufreq.cpufreq_modify_policy_max.restype = c_int

_libcpufreq.cpufreq_modify_policy_governor.argtypes = [c_uint, c_char_p]
_libcpufreq.cpufreq_modify_policy_governor.restype = c_int

_libcpufreq.cpufreq_set_frequency.argtypes = [c_uint, c_ulong]
_libcpufreq.cpufreq_set_frequency.restype = c_int

def cpu_exists(cpu):
	return _libcpufreq.cpufreq_cpu_exists(cpu)

def get_freq_kernel(cpu):
	return _libcpufreq.cpufreq_get_freq_kernel(cpu)

def get_freq_hardware(cpu):
	return _libcpufreq.cpufreq_get_freq_hardware(cpu)

def get_transition_latency(cpu):
	return _libcpufreq.cpufreq_get_transition_latency(cpu)

def get_hardware_limits(cpu):
	min = c_ulong()
	max = c_ulong()
	_libcpufreq.cpufreq_get_hardware_limits(cpu, byref(min), byref(max))
	return (min.value, max.value)

def get_driver(cpu):
	return _libcpufreq.cpufreq_get_driver(cpu).decode()

def get_policy(cpu):
	p = _libcpufreq.cpufreq_get_policy(cpu)
	policy = (p.contents.min, p.contents.max, p.contents.governor.decode())
	_libcpufreq.cpufreq_put_policy(p)
	return policy

def _marshall_structs(first, field, decode=False):
	values = []
	p = first
	while p:
		if decode:
			values.append(getattr(p.contents, field).decode())
		else:
			values.append(getattr(p.contents, field))
		p = p.contents.next
	return values

def get_available_governors(cpu):
	structs = _libcpufreq.cpufreq_get_available_governors(cpu)
	values = _marshall_structs(structs, 'governor', decode=True)
	_libcpufreq.cpufreq_put_available_governors(structs)
	return values

def get_available_frequencies(cpu):
	structs = _libcpufreq.cpufreq_get_available_frequencies(cpu)
	values = _marshall_structs(structs, 'frequency')
	_libcpufreq.cpufreq_put_available_frequencies(structs)
	return values

def get_affected_cpus(cpu):
	structs = _libcpufreq.cpufreq_get_affected_cpus(cpu)
	values = _marshall_structs(structs, 'cpu')
	_libcpufreq.cpufreq_put_affected_cpus(structs)
	return values

def get_related_cpus(cpu):
	structs = _libcpufreq.cpufreq_get_related_cpus(cpu)
	values = _marshall_structs(structs, 'cpu')
	_libcpufreq.cpufreq_put_related_cpus(structs)
	return values

def get_stats(cpu):
	total_time = c_ulonglong()
	p = _libcpufreq.cpufreq_get_stats(cpu, byref(total_time))
	stats = []
	while p:
		stats.append((p.contents.frequency, p.contents.time_in_state))
		p = p.contents.next
	_libcpufreq.cpufreq_put_stats(p)
	return total_time.value, stats

def get_transitions(cpu):
	return _libcpufreq.cpufreq_get_transitions(cpu)

def set_policy(cpu, min, max, governor):
	return _libcpufreq.cpufreq_set_policy(cpu, _cpufreq_policy(min, max, governor))

def modify_policy_min(cpu, min_freq):
	return _libcpufreq.cpufreq_modify_policy_min(cpu, min_freq)

def modify_policy_min(cpu, max_freq):
	return _libcpufreq.cpufreq_modify_policy_max(cpu, max_freq)

def modify_policy_governor(cpu, governor):
	return _libcpufreq.cpufreq_modify_policy_governor(cpu, governor.encode())

def set_frequency(cpu, target_frequency):
	return _libcpufreq.cpufreq_set_frequency(cpu, target_frequency)

def get_maxcpu():
	maxcpu = 0
	while cpu_exists(maxcpu) == 0:
		maxcpu += 1
	return maxcpu

def get_available_frequencies2(cpu):
	f_min, f_max = get_hardware_limits(0)
	out = list(range(f_min, f_max, 100000))+[f_max]
	return list(set(out))

def set_frequency2(cpu, freq):
	try:
		for i in range(get_maxcpu()):
			with open('/sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq'%i,'w') as fp:
				print(freq, file=fp, flush=True)
		return 0
	except:
		return -1

def get_frequency(cpu):
	try:
		with open('/sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq'%cpu) as fp:
			return int(fp.read().strip())
	except:
		pass
	return -1

if not get_available_frequencies(0):
	get_available_frequencies = get_available_frequencies2
	set_frequency = set_frequency2
	get_freq_hardware = get_freq_kernel = get_frequency
