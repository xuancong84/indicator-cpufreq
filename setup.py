#! /usr/bin/env python3

import DistUtilsExtra.auto
import glob
import os
from DistUtilsExtra.command import *

DistUtilsExtra.auto.setup(
    name='indicator-cpufreq',
    version='0.2.2',
    license='GPL-3',
    author='Artem Popov',
    author_email='artfwo@gmail.com',
    description='CPU frequency scaling indicator',
    long_description='Indicator applet for displaying and changing CPU frequency on-the-fly.',
    url='https://launchpad.net/indicator-cpufreq',
    # install icons as data_files because distutils don't do that well
    data_files=[
        ('share/icons/ubuntu-mono-dark/status/22',
            glob.glob('icons/ubuntu-mono-dark/*')),
        ('share/icons/ubuntu-mono-light/status/22',
            glob.glob('icons/ubuntu-mono-light/*')),
        # temp fix for LP: #1125598
        ('share/icons/hicolor/22x22/status',
            glob.glob('icons/ubuntu-mono-dark/*')),
#        ('/var/lib/polkit-1/localauthority/10-vendor.d',
#            ['indicator-cpufreq.pkla']),
    ]
)
