import os
import sys

try:
    from setuptools import setup
except:
    from distutils.core import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README')).read()

setup(name='rt',
    version='1.0.0',
    description='Python interface to Request Tracker API',
    long_description=README,
    license='GNU General Public License (GPL)',
    author='Jiri Machalek',
    author_email='jiri.machalek@nic.cz',
    url='https://github.com/machalekj/rt',
    install_requires=['requests'],
    py_modules=['rt'],
    )

