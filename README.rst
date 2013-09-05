==============================================
 Rt - Python interface to Request Tracker API 
==============================================

Python implementation of REST API described here:
http://requesttracker.wikia.com/wiki/REST

REQUIREMENTS
============

This module uses following Python modules:

- re
- os
- requests (http://docs.python-requests.org/)

LICENCE
=======

This module is distributed under the terms of GNU General Public Licence v3
and was developed by CZ.NIC Labs - research and development department of
CZ.NIC association - top level domain registy for .CZ.  Copy of the GNU
General Public License is distibuted along with this program.

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
This module was developed as a part of Malicious Domain Manager (MDM),
but can be used separately and also has its own Redmine project. We will
make the best effort to keep the changes synchronized in both projects.

python-rt module
    https://gitlab.labs.nic.cz/labs/python-rt
Malicious Domain Manager
    https://gitlab.labs.nic.cz/labs/mdm

