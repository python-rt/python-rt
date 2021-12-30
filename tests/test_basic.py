"""Tests for python-rt / REST2 - Python interface to Request Tracker :term:`API`."""

__license__ = """ Copyright (C) 2013 CZ.NIC, z.s.p.o.
    Copyright (c) 2021 CERT Gouvernemental (GOVCERT.LU)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
__docformat__ = "reStructuredText en"
__authors__ = [
    '"Jiri Machalek" <jiri.machalek@nic.cz>',
    '"Georges Toth" <georges.toth@govcert.etat.lu>',
]

import base64
import random
import string

import requests.auth

import rt.rest2
import rt.exceptions

RT_URL = 'http://localhost:8080/REST/2.0/'
RT_USER = 'root'
RT_PASSWORD = 'password'
RT_QUEUE = 'General'

c = rt.rest2.Rt(url=RT_URL, http_auth=requests.auth.HTTPBasicAuth(RT_USER, RT_PASSWORD))


def test_login():
    assert c.login()

    # bad login
    _c = rt.rest2.Rt(url=RT_URL, http_auth=requests.auth.HTTPBasicAuth(RT_USER, f'{RT_PASSWORD}123'))
    assert _c.login() is False


def test_get_user():
    user = c.get_user(RT_USER)
    assert user['Name'] == RT_USER
    assert '@' in user['EmailAddress']
    assert user['Privileged'] == 1


def test_ticket_operations():
    ticket_subject = 'Testing issue ' + "".join([random.choice(string.ascii_letters) for i in range(15)])
    ticket_text = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'

    # empty search result
    search_result = c.search(Subject=ticket_subject)
    assert not len(search_result)

    # create
    ticket_id = c.create_ticket(Subject=ticket_subject, Content=ticket_text, Queue=RT_QUEUE)
    assert ticket_id > -1

    # search
    search_result = c.search(Subject=ticket_subject)
    assert len(search_result) == 1
    assert search_result[0]['id'] == str(ticket_id)
    assert search_result[0]['Status'] == 'new'

    # # raw search
    search_result = c.search(raw_query=f'Subject="{ticket_subject}"')
    assert len(search_result) == 1
    assert search_result[0]['id'] == str(ticket_id)
    assert search_result[0]['Status'] == 'new'

    # get ticket
    ticket = c.get_ticket(ticket_id)
    search_result[0]['id'] = int(search_result[0]['id'])

    for k in search_result[0]:
        if k.startswith('_') or k in ('type', 'CustomFields'):
            continue

        assert k in ticket
        assert ticket[k] == search_result[0][k]

    # edit ticket
    requestors = ['tester1@example.com', 'tester2@example.com']
    c.edit_ticket(ticket_id, Status='open', Requestor=requestors)

    # get ticket (edited)
    ticket = c.get_ticket(ticket_id)
    assert ticket['Status'] == 'open'
    for requestor in ticket['Requestor']:
        assert requestor['id'] in requestors
    for requestor in requestors:
        found = False
        for _requestor in ticket['Requestor']:
            if _requestor['id'] == requestor:
                found = True
                break

        assert found

    # get history
    hist = c.get_ticket_history(ticket_id)
    assert len(hist) > 0
    transaction = c.get_transaction(hist[0]['id'])
    found = False
    for hyperlink in transaction['_hyperlinks']:
        if hyperlink['ref'] == 'attachment':
            attachment_id = hyperlink['_url'].rsplit('/', 1)[1]
            attachment = base64.b64decode(c.get_attachment(attachment_id)['Content']).decode('utf-8')
            found = True
            assert attachment == ticket_text
            break

    assert found

    # get_short_history
    short_hist = c.get_ticket_history(ticket_id)
    assert len(short_hist) > 0
    assert short_hist[0]['Type'] == 'Create'
    assert short_hist[0]['Creator']['Name'] == RT_USER

    # create 2nd ticket
    ticket2_subject = 'Testing issue ' + "".join([random.choice(string.ascii_letters) for i in range(15)])
    ticket2_id = c.create_ticket(Queue=RT_QUEUE, Subject=ticket2_subject)
    assert ticket2_id > -1

    # edit link
    assert c.edit_link(ticket_id, 'DependsOn', ticket2_id)

    # get links
    links1 = c.get_links(ticket_id)
    found = False
    for link in links1:
        if link['ref'] == 'depends-on' and link['id'] == str(ticket2_id):
            found = True
    assert found

    links2 = c.get_links(ticket2_id)
    found = False
    for link in links2:
        if link['ref'] == 'depended-on-by' and link['id'] == str(ticket_id):
            found = True
    assert found

    # reply with attachment
    attachment_content = b'Content of attachment.'
    attachment_name = 'attachment-name.txt'
    reply_text = 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.'
    attachment = rt.rest2.Attachment(attachment_name, 'text/plain', attachment_content)
    # should provide a content type as RT 4.0 type guessing is broken (missing use statement for guess_media_type in REST.pm)
    assert c.reply(ticket_id, text=reply_text, attachments=[attachment])

    # attachments list
    at_list = c.get_attachments(ticket_id)
    assert at_list
    at_names = [at['Filename'] for at in at_list]
    assert attachment_name in at_names
    # get the attachment and compare it's content
    at_id = at_list[at_names.index(attachment_name)]['id']
    at_content = base64.b64decode(c.get_attachment(at_id)['Content'])
    assert at_content == attachment_content

    # merge tickets
    assert c.merge_ticket(ticket2_id, ticket_id)

    # delete ticket
    assert c.edit_ticket(ticket_id, Status='deleted')
