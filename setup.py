#!/usr/bin/env python3

import sys
import distutils.util
try:
    # First try to load most advanced setuptools setup.
    from setuptools import setup
except:
    # Fall back if setuptools is not installed.
    from distutils.core import setup

# check linux platform
platform = distutils.util.get_platform()
if not platform.startswith('linux'):
    sys.stderr.write("This module is not available on %s\n" % platform)
    sys.exit(1)

classif = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GPLv3 License',
    'Natural Language :: English',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

# Do setup
setup(
    name='libmirrors',
    version='0.0.1',
    description='Operating passwd/group/shadow in a strict manner',
    author='Fpemud',
    author_email='fpemud@sina.com',
    license='GPLv3 License',
    platforms='Linux',
    classifiers=classif,
    url='http://github.com/fpemud/strict_pgs',
    download_url='',
    py_modules=['strict_pgs'],
    package_dir={'': 'python3'},
)
