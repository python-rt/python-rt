Usage
=====

REST API version 2
-------------------

Creating a Connection
`````````````````````
::

    import rt.rest2

    api_url = 'http://localhost:8080/REST/2.0/'
    username = 'root'
    password = 'password'
    c = rt.rest2.Rt(url=baseurl, http_auth=requests.auth.HTTPBasicAuth('root', 'password'))


Ticket Operations
`````````````````

Fetching a ticket::

    c.get_ticket(1)

which gives:

.. code-block:: json

    {
        "Due": "1970-01-01T00:00:00Z",
        "Status": "new",
        "Created": "2022-05-02T18:54:36Z",
        "CustomFields": [],
        "TimeEstimated": "0",
        "LastUpdatedBy": {
            "id": "root",
            "type": "user",
            "_url": "http://localhost:8080/REST/2.0/user/root"
        },
        "Type": "ticket",
        "Owner": {
            "id": "Nobody",
            "_url": "http://localhost:8080/REST/2.0/user/Nobody",
            "type": "user"
        },
        "Cc": [],
        "Started": "1970-01-01T00:00:00Z",
        "AdminCc": [],
        "Priority": "0",
        "LastUpdated": "2022-05-02T19:21:30Z",
        "Subject": "Testing issue wvbocycTSwmNTAX",
        "FinalPriority": "0",
        "Queue": {
            "id": "1",
            "type": "queue",
            "_url": "http://localhost:8080/REST/2.0/queue/1",
            "Name": "General"
        },
        "InitialPriority": "0",
        "Resolved": "1970-01-01T00:00:00Z",
        "Creator": {
            "type": "user",
            "_url": "http://localhost:8080/REST/2.0/user/root",
            "id": "root"
        },
        "EffectiveId": {
            "_url": "http://localhost:8080/REST/2.0/ticket/8",
            "type": "ticket",
            "id": "8"
        },
        "Starts": "1970-01-01T00:00:00Z",
        "TimeWorked": "0",
        "TimeLeft": "0",
        "Requestor": [],
        "_hyperlinks": [
            {
                "id": 8,
                "ref": "self",
                "_url": "http://localhost:8080/REST/2.0/ticket/8",
                "type": "ticket"
            },
            {
                "ref": "history",
                "_url": "http://localhost:8080/REST/2.0/ticket/8/history"
            },
            {
                "_url": "http://localhost:8080/REST/2.0/ticket/8/correspond",
                "ref": "correspond"
            },
            {
                "ref": "comment",
                "_url": "http://localhost:8080/REST/2.0/ticket/8/comment"
            },
            {
                "ref": "lifecycle",
                "update": "Respond",
                "from": "new",
                "label": "Open It",
                "_url": "http://localhost:8080/REST/2.0/ticket/8/correspond",
                "to": "open"
            },
            {
                "label": "Resolve",
                "to": "resolved",
                "_url": "http://localhost:8080/REST/2.0/ticket/8/comment",
                "ref": "lifecycle",
                "update": "Comment",
                "from": "new"
            },
            {
                "to": "rejected",
                "_url": "http://localhost:8080/REST/2.0/ticket/8/correspond",
                "label": "Reject",
                "from": "new",
                "update": "Respond",
                "ref": "lifecycle"
            },
            {
                "ref": "lifecycle",
                "label": "Delete",
                "_url": "http://localhost:8080/REST/2.0/ticket/8",
                "from": "new",
                "to": "deleted"
            }
        ],
        "id": 8
    }


Getting ticket links::

    c.get_links(1)

for a ticket with #1 having ticket #7 as parent, this would have as result:

.. code-block:: json

    [
        {
            "_url": "http://localhost:8080/REST/2.0/ticket/7",
            "type": "ticket",
            "ref": "parent",
            "id": "7"
        }
    ]

Editing ticket links. Adding a dependency on another ticket::

    c.edit_link(1, 'DependsOn', 7, delete=False)

Creating a ticket::

    new_ticket = {'Requestor': ['test@example.com'],
                  }
    res = c.create_ticket('General',
                          subject='Test subject',
                          content='Ticket body...',
                          **new_ticket
                          )

This returns the ID of the created ticket.

Editing a ticket::

    c.edit_ticket(8,
                  Subject='Re: Test subject',
                  CustomFields={'CF1': 'value1',
                                ...
                                }
                  )


Searching for tickets with status *NEW* in the *General* queue::

    c.search(Queue='SOC', raw_query='''Status = 'NEW' ''', Format='i')

gives:

.. code-block:: json

    [
        {
            "type": "ticket",
            "InitialPriority": "0",
            "CustomFields": "",
            "TimeEstimated": "0",
            "Due": "1970-01-01T00:00:00Z",
            "Priority": "0",
            "Status": "new",
            "Created": "2022-05-02T18:54:35Z",
            "Queue": {
                "Name": "General",
                "type": "queue",
                "_url": "http://localhost:8080/REST/2.0/queue/1",
                "id": "1"
            },
            "Subject": "Testing issue SsOwRvDXMGnurhU",
            "LastUpdated": "2022-05-02T20:44:02Z",
            "TimeLeft": "0",
            "Owner": {
                "id": "Nobody",
                "_url": "http://localhost:8080/REST/2.0/user/Nobody",
                "type": "user"
            },
            "Started": "1970-01-01T00:00:00Z",
            "Requestor": [],
            "Cc": [],
            "AdminCc": [],
            "id": "7",
            "_url": "http://localhost:8080/REST/2.0/ticket/7",
            "Type": "ticket"
        },
        ...
    ]

Do a reply on a ticket::

    c.reply(1, content='test')

Comment on a ticket::

    c.comment(1, content='test')

Merge ticket #1 into #2::

    c.merge_ticket(1, 2)

Comment on a ticket and add an attachment::

    attachments = []
    with open('README.rst', 'rb') as fhdl:
        attachments.append(rt.rest2.Attachment('README.rst', 'test/plain', fhdl.read()))
    print(json.dumps(c.comment(1, 'test', attachments=attachments), indent=4))


Get attachments for a ticket::

    c.get_attachments(1)

returns:

.. code-block:: json

    [
        {
            "type": "attachment",
            "_url": "http://localhost:8080/REST/2.0/attachment/34",
            "Filename": "README.rst",
            "ContentType": "test/plain",
            "id": "34",
            "ContentLength": "3578"
        }
    ]

Fetch an attachment by its ID::

    c.get_attachment(34)
