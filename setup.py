import os
import sys

try:
    from setuptools import setup
except:
    from distutils.core import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()

setup(name='rt',
    version='1.0.post6',
    description='Python interface to Request Tracker API',
    long_description=README,
    license='GNU General Public License (GPL)',
    author='Jiri Machalek',
    author_email='jiri.machalek@nic.cz',
    url='https://gitlab.labs.nic.cz/labs/python-rt',
    install_requires=['requests'],
    py_modules=['rt'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.2',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)

