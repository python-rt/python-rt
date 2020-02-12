           
.. image:: https://travis-ci.org/CZ-NIC/python-rt.svg?branch=master
    :target: https://travis-ci.org/CZ-NIC/python-rt
.. image:: https://readthedocs.org/projects/python-rt/badge/?version=latest
    :target: https://python-rt.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

==============================================
 Rt - Python interface to Request Tracker API 
==============================================

Python implementation of REST API described here: https://rt-wiki.bestpractical.com/wiki/REST

**Note:** Please note that starting with the major release of v2.0.0, this library requires a Python version >= 3.5.
In case you still require a Python 2 version or one compatible with Python < 3.5, please use a version < 2.0.0 of this library.


REQUIREMENTS
============

This module uses following Python modules:

- requests (http://docs.python-requests.org/)

Unit-tests are implemented using:
- nose (http://nose.readthedocs.org)


INSTALLATION
============

Install the python-rt package using::

  pip install rt


LICENCE
=======

This module is distributed under the terms of GNU General Public Licence v3
and was developed by CZ.NIC Labs - research and development department of
CZ.NIC association - top level domain registy for .CZ.  Copy of the GNU
General Public License is distributed along with this module.

USAGE
=====

An example is worth a thousand words::

    >>> import rt
    >>> tracker = rt.Rt('http://localhost/rt/REST/1.0/', 'user_login', 'user_pass')
    >>> tracker.login()
    True
    >>> map(lambda x: x['id'], tracker.search(Queue='helpdesk', Status='open'))
    ['ticket/1', 'ticket/2', 'ticket/10', 'ticket/15']
    >>> tracker.create_ticket(Queue='helpdesk', \
    ... Subject='Coffee (important)', Text='Help I Ran Out of Coffee!')
    19
    >>> tracker.edit_ticket(19, Requestors='addicted@example.com')
    True
    >>> tracker.reply(19, text='Do you know Starbucks?')
    True
    >>> tracker.logout()
    True

Please use docstrings to see how to use different functions. They are written
in ReStructuredText. You can also generate HTML documentation by running
``make html`` in doc directory (Sphinx required).

OFFICIAL SITE
=============

Project site and issue tracking:
    https://github.com/CZ-NIC/python-rt

Git repository:
    git://github.com/CZ-NIC/python-rt.git    
    
