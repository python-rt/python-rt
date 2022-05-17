.. image:: https://codebeat.co/badges/a52cfe15-b824-435b-a594-4bf2be2fb06f
    :target: https://codebeat.co/projects/github-com-python-rt-python-rt-master
    :alt: codebeat badge
.. image:: https://github.com/python-rt/python-rt/actions/workflows/test_lint.yml/badge.svg
    :target: https://github.com/python-rt/python-rt/actions/workflows/test_lint.yml
    :alt: tests
.. image:: https://readthedocs.org/projects/python-rt/badge/?version=stable
    :target: https://python-rt.readthedocs.io/en/stable/?badge=stable
    :alt: Documentation Status
.. image:: https://badge.fury.io/py/rt.svg
    :target: https://badge.fury.io/py/rt

==============================================
 Rt - Python interface to Request Tracker API 
==============================================

Python implementation of REST API described here:
 - https://rt-wiki.bestpractical.com/wiki/REST
 - https://docs.bestpractical.com/rt/5.0.2/RT/REST2.html

.. csv-table:: Python version compatibility:
   :header: "Python", "rt"
   :widths: 15, 15

   "2.7", "< 2.0.0"
   ">= 3.5, <3.7", ">= 2.0.0, < 3.0.0"
   ">= 3.7", ">= 3.0.0"

ℹ️ **Note**:
    Please note that starting with the major release of v3.0.0, this library requires Python version >= 3.7.
    See the *Python version compatibility* table above for more detailed information.

⚠️ **Warning**:
    Though version 3.x still supports RT REST API version 1, it contains minor breaking changes. Please see the changelog
    in the documentation for details.

Requirements
============

This module uses following Python modules:
 - requests (http://docs.python-requests.org/)
 - requests-toolbelt (https://pypi.org/project/requests-toolbelt/)
 - typing-extensions (depending on python version)

Documentation
=============
https://python-rt.readthedocs.io/en/latest/

Installation
============

Install the python-rt package using::

  pip install rt


Licence
=======

This module is distributed under the terms of GNU General Public Licence v3
and was developed by CZ.NIC Labs - research and development department of
CZ.NIC association - top level domain registry for .CZ.  Copy of the GNU
General Public License is distributed along with this module.

Usage
=====

An example is worth a thousand words::

    >>> import rt.rest2
    >>> import requests.auth
    >>> tracker = rt.rest2.Rt('http://localhost/rt/REST/2.0/', http_auth=requests.auth.HTTPBasicAuth('root', 'password'))
    >>> map(lambda x: x['id'], tracker.search(Queue='helpdesk', Status='open'))
    ['1', '2', '10', '15']
    >>> tracker.create_ticket(queue='helpdesk', \
    ... subject='Coffee (important)', content='Help I Ran Out of Coffee!')
    19
    >>> tracker.edit_ticket(19, Requestor='addicted@example.com')
    True
    >>> tracker.reply(19, content='Do you know Starbucks?')
    True

Get the last important updates from a specific queue that have been updated recently::

    >>> import datetime
    >>> import base64
    >>> import rt.rest2
    >>> import requests.auth
    >>> tracker = rt.rest2.Rt('http://localhost/rt/REST/2.0/', http_auth=requests.auth.HTTPBasicAuth('root', 'password'))
    >>> fifteen_minutes_ago = str(datetime.datetime.now() - datetime.timedelta(minutes=15))
    >>> tickets = tracker.last_updated(since=fifteen_minutes_ago)
    >>> for ticket in tickets:
    >>>     id = ticket['id']
    >>>     history = tracker.get_ticket_history(id)
    >>>     last_update = list(reversed([h for h in history if h['Type'] in ('Correspond', 'Comment')]))
    >>>     hid = tracker.get_transaction(last_update[0]['id'] if last_update else history[0]['id'])
    >>>
    >>>     attachment_id = None
    >>>     for k in hid['_hyperlinks']:
    >>>         if k['ref'] == 'attachment':
    >>>             attachment_id = k['_url'].rsplit('/', 1)[1]
    >>>             break
    >>>
    >>>         if attachment_id is not None:
    >>>             attachment = c.get_attachment(attachment_id)
    >>>             if attachment['Content'] is not None:
    >>>                 content = base64.b64decode(attachment['Content']).decode()
    >>>                 print(content)


		
Please use docstrings to see how to use different functions. They are written
in ReStructuredText. You can also generate HTML documentation by running
``make html`` in doc directory (Sphinx required).

Official Site
=============

Project site, issue tracking and git repository:
    https://github.com/python-rt/python-rt
