"""Python interface to Request Tracker :term:`API`

Description of Request Tracker :term:`REST2` :term:`API`:
https://docs.bestpractical.com/rt/5.0.0/RT/REST2.html
"""

import base64
import dataclasses
import datetime
import logging
import re
import typing
from urllib.parse import urljoin

import requests
import requests.auth

import rt.exceptions
from .exceptions import AuthorizationError, UnexpectedResponse, NotFoundError, InvalidUse

__license__ = """ Copyright (C) 2012 CZ.NIC, z.s.p.o.
    Copyright (c) 2015 Genome Research Ltd.
    Copyright (c) 2017 CERT Gouvernemental (GOVCERT.LU)

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
    '"Joshua C. randall" <jcrandall@alum.mit.edu>',
    '"Georges Toth" <georges.toth@govcert.etat.lu>',
]

VALID_TICKET_LINK_NAMES = ('Parent', 'Child', 'RefersTo',
                           'ReferredToBy', 'DependsOn', 'DependedOnBy')


@dataclasses.dataclass
class Attachment:
    """Dataclass representing an attachment."""

    file_name: str
    file_type: str
    file_content: bytes

    def to_dict(self) -> typing.Dict[str, str]:
        """Convert to a dictionary for submitting to the REST API."""
        return {'FileName': self.file_name,
                'FileType': self.file_type,
                'FileContent': base64.b64encode(self.file_content).decode('utf-8')
                }


class Rt:
    """ :term:`API` for Request Tracker according to
    https://docs.bestpractical.com/rt/5.0.0/RT/REST2.html. Interface is based on
    :term:`REST` architecture, which is based on HTTP/1.1 protocol. This module
    is therefore mainly sending and parsing special HTTP messages.

    .. note:: Use only ASCII LF as newline (``\\n``). Time is returned in UTC.
              All strings returned are encoded in UTF-8 and the same is
              expected as input for string values.
    """

    def __init__(self, url: str,
                 proxy: typing.Optional[str] = None,
                 verify_cert: typing.Optional[typing.Union[str, bool]] = True,
                 http_auth: typing.Optional[requests.auth.AuthBase] = None,
                 token: typing.Optional[str] = None,
                 http_timeout: typing.Optional[int] = 20,
                 ) -> None:
        """ API initialization.

        :keyword url: Base URL for Request Tracker API.
                      E.g.: http://tracker.example.com/REST/2.0/
        :keyword proxy: Proxy server (string with http://user:password@host/ syntax)
        :keyword http_auth: Specify a http authentication instance, e.g. HTTPBasicAuth(), HTTPDigestAuth(),
                            etc. to be used for authenticating to RT
        :keyword token: Optional authentication token to be used instead of basic authentication.
        :keyword http_timeout: HTTP timeout after which a request is aborted.
        """
        self.logger = logging.getLogger(__name__)

        # ensure trailing slash
        if not url.endswith('/'):
            url = f'{url}/'

        if not url.endswith('REST/2.0/'):
            raise ValueError('Invalid REST URL specified, please use a form of https://example.com/REST/2.0/')

        self.url = url
        self.base_url = url.split('REST/2.0/', 1)[0]

        self.session = requests.session()
        self.session.verify = verify_cert

        if proxy is not None:  # pragma: no cover
            if url.lower().startswith("https://"):
                self.session.proxies = {"https": proxy}
            else:
                self.session.proxies = {"http": proxy}
        if http_auth is not None:
            self.session.auth = http_auth
        if token is not None:  # pragma: no cover  # no way to add tests for this with the current docker image
            self.session.headers['Authorization'] = f'token {token}'

        self.http_timeout = http_timeout

    def __debug_response(self, response: requests.Response) -> None:
        """Output debug info for an HTTP response."""
        self.logger.debug("### %s", datetime.datetime.now().isoformat())
        self.logger.debug("Request URL: %s", response.request.url)
        self.logger.debug("Request method: %s", response.request.method)
        self.logger.debug("Request headers: %s", response.request.headers)
        self.logger.debug("Request body: %s", str(response.request.body))
        self.logger.debug("Response status code: %s", str(response.status_code))
        self.logger.debug("Response content:")
        self.logger.debug(response.content.decode())

    def __request(self,
                  selector: str,
                  get_params: typing.Optional[typing.Dict[str, typing.Any]] = None,
                  json_data: typing.Optional[typing.Union[typing.Dict[str, typing.Any], typing.List[typing.Any]]] = None,
                  post_data: typing.Optional[typing.Dict[str, typing.Any]] = None,
                  files: typing.Optional[typing.Dict[str, str]] = None,
                  ) -> typing.Dict[str, typing.Any]:
        """ General request for :term:`API`.

        :keyword selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :keyword get_params: Parameters to add for a GET request.
        :keyword json_data: JSON request to send to the API.
        :keyword post_data: Dictionary with POST method fields
        :keyword files: List of pairs (filename, file-like object) describing
                        files to attach as multipart/form-data
                        (list is necessary to keep files ordered)
        :returns: dict
        :rtype: dict
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        try:
            url = str(urljoin(self.url, selector))
            if not files:
                if json_data:
                    response = self.session.post(url, json=json_data, timeout=self.http_timeout)
                elif post_data:
                    response = self.session.post(url, data=post_data, timeout=self.http_timeout)
                else:
                    response = self.session.get(url, params=get_params, timeout=self.http_timeout)
            else:
                response = self.session.post(url, data=post_data, files=files, timeout=self.http_timeout)

            self.__debug_response(response)
            self.__check_response(response)

            try:
                result = response.json()
            except LookupError:  # pragma: no cover
                raise UnexpectedResponse(f'Unknown response encoding: {response.encoding}.')
            except UnicodeError:  # pragma: no cover
                raise UnexpectedResponse(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''')

            return result
        except requests.exceptions.ConnectionError as e:  # pragma: no cover
            raise ConnectionError("Connection error", e)

    def __request_put(self,
                      selector: str,
                      json_data: typing.Optional[typing.Dict[str, typing.Any]] = None
                      ) -> typing.List[str]:
        """ General request for :term:`API`.

        :keyword selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :keyword json_data: JSON request to send to the API.
        :returns: dict
        :rtype: dict
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        try:
            url = str(urljoin(self.url, selector))

            _headers = dict(self.session.headers)
            _headers['Content-Type'] = 'application/json'
            response = self.session.put(url, json=json_data, headers=_headers, timeout=self.http_timeout)

            self.__debug_response(response)
            self.__check_response(response)

            try:
                result = response.json()
            except LookupError:  # pragma: no cover
                raise UnexpectedResponse(f'Unknown response encoding: {response.encoding}.')
            except UnicodeError:  # pragma: no cover
                raise UnexpectedResponse(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''')

            return result
        except requests.exceptions.ConnectionError as e:  # pragma: no cover
            raise ConnectionError("Connection error", e)

    def __request_delete(self,
                         selector: str,
                         ) -> typing.Dict[str, str]:
        """ General request for :term:`API`.

        :keyword selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``

        :returns: dict
        :rtype: dict
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        try:
            url = str(urljoin(self.url, selector))

            _headers = dict(self.session.headers)
            _headers['Content-Type'] = 'application/json'
            response = self.session.delete(url, headers=_headers, timeout=self.http_timeout)

            self.__debug_response(response)
            self.__check_response(response)

            try:
                result = response.json()
            except LookupError:  # pragma: no cover
                raise UnexpectedResponse(f'Unknown response encoding: {response.encoding}.')
            except UnicodeError:  # pragma: no cover
                raise UnexpectedResponse(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''')

            return result
        except requests.exceptions.ConnectionError as e:  # pragma: no cover
            raise ConnectionError("Connection error", e)

    def __paged_request(self,
                        selector: str,
                        json_data: typing.Optional[typing.Union[typing.List[typing.Dict[str, typing.Any]], typing.Dict[str, typing.Any]]] = None,
                        params: typing.Optional[typing.Dict[str, typing.Any]] = None,
                        page: int = 1,
                        per_page: int = 10,
                        recurse: bool = True
                        ) -> typing.Iterator[typing.Dict[str, typing.Any]]:
        """ General request for :term:`API`.

        :keyword selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :keyword json_data: JSON request to send to the API.
        :keyword page: The page number to get.
        :keyword per_page: Number of results per page to get.
        :keyword recurse: Set on the initial call in order to retrieve all pages recursively.

        :returns: dict
        :rtype: iterator
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        if params:
            params['page'] = page
            params['per_page'] = per_page
        else:
            params = {'page': page, 'per_page': per_page}

        try:
            url = str(urljoin(self.url, selector))

            method = 'get'
            if json_data is not None:
                method = 'post'

            response = self.session.request(method, url, json=json_data, params=params, timeout=self.http_timeout)

            self.__check_response(response)

            try:
                result = response.json()
            except LookupError:  # pragma: no cover
                raise UnexpectedResponse(f'Unknown response encoding: {response.encoding}.')
            except UnicodeError:  # pragma: no cover
                # replace errors - we need decoded content just to check for error codes in __check_response
                result = response.content.decode('utf-8', 'replace')

            if not isinstance(result, dict) and 'items' in result:
                raise UnexpectedResponse('Server returned an unexpected result')

            yield from result['items']

            if recurse and result['pages'] > result['page']:
                for _page in range(2, result['pages'] + 1):
                    yield from self.__paged_request(selector, json_data=json_data, page=_page,
                                                    per_page=result['per_page'], params=params, recurse=False)

        except requests.exceptions.ConnectionError as e:  # pragma: no cover
            raise ConnectionError("Connection error", e)

    @staticmethod
    def __check_response(response: requests.Response) -> None:
        """ Search general errors in server response and raise exceptions when found.

        :keyword response: Response from HTTP request.
        :raises AuthorizationError: Credentials are invalid or missing
        :raises NotFoundError: Resource was not found.
        :raises UnexpectedResponse: Server returned an unexpected status code.
        """
        if response.status_code == 401:  # pragma: no cover
            raise AuthorizationError(
                'Server could not verify that you are authorized to access the requested document.')
        if response.status_code == 404:
            raise NotFoundError('No such resource found.')
        if response.status_code not in (200, 201):
            raise UnexpectedResponse('Received status code {:d} instead of 200.'.format(response.status_code),
                                     status_code=response.status_code,
                                     response_message=response.text)

    def __get_url(self, url: str) -> typing.Dict[str, typing.Any]:
        """Call a URL as specified in the returned JSON of an API operation."""
        url_ = url.split('/REST/2.0/', 1)[1]
        return self.__request(url_)

    def new_correspondence(self, queue: typing.Optional[typing.Union[str, object]] = None) -> typing.List[dict]:
        """ Obtains tickets changed by other users than the system one.

        :keyword queue: Queue where to search

        :returns: List of tickets which were last updated by other user than
                  the system one ordered in decreasing order by LastUpdated.
                  Each ticket is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        return self.search(Queue=queue, order='-LastUpdated')

    def last_updated(self, since: str, queue: typing.Optional[str] = None) -> typing.List[dict]:
        """ Obtains tickets changed after given date.

        :param since: Date as string in form '2011-02-24'
        :keyword queue: Queue where to search

        :returns: List of tickets with LastUpdated parameter later than
                  *since* ordered in decreasing order by LastUpdated.
                  Each tickets is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        if not self.__validate_date(since):
            raise InvalidUse(f'Invalid date specified - "{since}"')

        return self.search(Queue=queue, order='-LastUpdated',
                           LastUpdated__gt=since)

    @classmethod
    def __validate_date(cls, _date: str) -> bool:
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', _date)
        if m:
            try:
                year = int(m.group(1))
                month = int(m.group(2))
                day = int(m.group(3))
            except ValueError:
                return False

            if 1970 < year < 2100 and 1 < month <= 12 and 1 < day <= 31:
                return True

        return False

    def search(self, Queue: typing.Optional[typing.Union[str, object]] = None, order: typing.Optional[str] = None,
               raw_query: typing.Optional[str] = None, Format: str = 'l', **kwargs: typing.Any) -> typing.List[dict]:
        """ Search arbitrary needles in given fields and queue.

        Example::

            >>> tracker = Rt('http://tracker.example.com/REST/2.0/', 'rt-username', 'top-secret')
            >>> tickets = tracker.search(CF_Domain='example.com', Subject__like='warning')
            >>> tickets = tracker.search(Queue='General', order='Status', raw_query="id='1'+OR+id='2'+OR+id='3'")

        :keyword Queue:      Queue where to search. If you wish to search across
                             all of your queues, pass the ALL_QUEUES object as the
                             argument.
        :keyword order:      Name of field sorting result list, for descending
                             order put - before the field name. E.g. -Created
                             will put the newest tickets at the beginning
        :keyword raw_query:  A raw query to provide to RT if you know what
                             you are doing. You may still pass Queue and order
                             kwargs, so use these instead of including them in
                             the raw query. You can refer to the RT query builder.
                             If passing raw_query, all other **kwargs will be ignored.
        :keyword Format:     Format of the query:
                               - i: only `id' fields are populated
                               - s: only `id' and `subject' fields are populated
                               - l: multi-line format, all fields are populated
        :keyword kwargs:     Other arguments possible to set if not passing raw_query:

                             Requestors, Subject, Cc, AdminCc, Owner, Status,
                             Priority, InitialPriority, FinalPriority,
                             TimeEstimated, Starts, Due, Text,... (according to RT
                             fields)

                             Custom fields CF.{<CustomFieldName>} could be set
                             with keywords CF_CustomFieldName.

                             To alter lookup operators you can append one of the
                             following endings to each keyword:

                             __exact    for operator = (default)
                             __notexact for operator !=
                             __gt       for operator >
                             __lt       for operator <
                             __like     for operator LIKE
                             __notlike  for operator NOT LIKE

                             Setting values to keywords constrain search
                             result to the tickets satisfying all of them.

        :returns: List of matching tickets. Each ticket is the same dictionary
                  as in :py:meth:`~Rt.get_ticket`.
        :raises:  UnexpectedMessageFormat: Unexpected format of returned message.
                  InvalidQueryError: If raw query is malformed
        """
        get_params = {}
        query = []
        url = 'tickets'

        if Queue is not None:
            query.append(f'Queue=\'{Queue}\'')
        if not raw_query:
            operators_map = {
                'gt': '>',
                'lt': '<',
                'exact': '=',
                'notexact': '!=',
                'like': ' LIKE ',
                'notlike': ' NOT LIKE '
            }

            for key, value in kwargs.items():
                op = '='
                key_parts = key.split('__')
                if len(key_parts) > 1:
                    key = '__'.join(key_parts[:-1])
                    op = operators_map.get(key_parts[-1], '=')
                if key[:3] != 'CF_':
                    query.append(f'{key}{op}\'{value}\'')
                else:
                    query.append("'CF.{{{}}}'{}\'{}\'".format(key[3:], op, value))
        else:
            query.append(raw_query)
        get_params['query'] = ' AND '.join('(' + part + ')' for part in query)
        if order:
            get_params['orderby'] = order

        if Format == 'l':
            get_params['fields'] = 'Owner,Status,Created,Subject,Queue,CustomFields,Requestor,Cc,AdminCc,Started,Created,TimeEstimated,Due,Type,InitialPriority,Priority,TimeLeft,LastUpdated'
            get_params['fields[Queue]'] = 'Name'
        elif Format == 's':
            get_params['fields'] = 'Subject'

        msgs = self.__request(url, get_params=get_params)

        return msgs['items']

    def get_ticket(self, ticket_id: typing.Union[str, int]) -> dict:
        """ Fetch ticket by its ID.

        :param ticket_id: ID of demanded ticket

        :returns: Dictionary with key, value pairs for ticket with
                  *ticket_id* or None if ticket does not exist. List of keys:

                      * id
                      * numerical_id
                      * Queue
                      * Owner
                      * Creator
                      * Subject
                      * Status
                      * Priority
                      * InitialPriority
                      * FinalPriority
                      * Requestors
                      * Cc
                      * AdminCc
                      * Created
                      * Starts
                      * Started
                      * Due
                      * Resolved
                      * Told
                      * TimeEstimated
                      * TimeWorked
                      * TimeLeft
        :raises UnexpectedMessageFormat: Unexpected format of returned message.
        :raises NotFoundError: If there is no ticket with the specified ticket_id.
        """
        return self.__request(f'ticket/{ticket_id}', get_params={'fields[Queue]': 'Name'})

    def create_ticket(self,
                      queue: str,
                      content_type: str = 'text/plain',
                      subject: typing.Optional[str] = None,
                      content: typing.Optional[str] = None,
                      attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                      **kwargs: typing.Any) -> int:
        """ Create new ticket and set given parameters.

        Example of message sent to ``http://tracker.example.com/REST/2.0/ticket/new``::

            { "Queue": "General",
              "Subject": "Ticket created through REST API",
              "Owner": "Nobody",
              "Requestor": "somebody@example.com",
              "Cc": "user2@example.com",
              "CustomRoles": {"My Role": "staff1@example.com"},
              "Content": "Lorem Ipsum",
              "CustomFields": {"Severity": "Low"}
            }

        + list of some key, value pairs, probably default values.

        :keyword queue: Queue where to create ticket
        :keyword content_type: Content-type of the Content parameter; can be either text/plain or text/html.
        :keyword subject: Optional subject for the ticket.
        :keyword content: Optional content of the ticket. Must be specified unless attachments are specified.
        :keyword attachments: Optional list of Attachment objects
        :keyword kwargs: Other arguments possible to set:

                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Content (according to RT
                         fields)

        :returns: ID of new ticket
        """
        if content_type not in ('text/plain', 'text/html'):  # pragma: no cover
            raise ValueError('Invalid content-type specified.')

        ticket_data: typing.Dict[str, typing.Any] = {'Queue': queue}

        if subject is not None:
            ticket_data['Subject'] = subject

        if content is not None:
            ticket_data['Content'] = content
            ticket_data['ContentType'] = content_type

        for k, v in kwargs.items():
            ticket_data[k] = v

        if attachments:
            ticket_data['Attachments'] = [attachment.to_dict() for attachment in attachments]

        res = self.__request('ticket', json_data=ticket_data)

        return int(res['id'])

    def edit_ticket(self, ticket_id: typing.Union[str, int], **kwargs: typing.Any) -> bool:
        """ Edit ticket values.

        :param ticket_id: ID of ticket to edit
        :keyword kwargs: Other arguments possible to set:

                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Text,... (according to RT
                         fields)

                         Custom fields can be specified as dict:
                            CustomFields = {"Severity": "Low"}

        :returns: ``True``
                      Operation was successful
                  ``False``
                      Ticket with given ID does not exist or unknown parameter
                      was set (in this case all other valid fields are changed)
        """
        msg = self.__request_put(f'ticket/{ticket_id}', json_data=kwargs)

        self.logger.debug(msg)

        if not (isinstance(msg, list) and len(msg) >= 1):  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        return bool(msg[0])

    def get_ticket_history(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Dict[str, typing.Any]]]:
        """ Get set of short history items

        :param ticket_id: ID of ticket
        :returns: List of history items ordered increasingly by time of event.
                  Each history item is a tuple containing (id, Description).
                  Returns None if ticket does not exist.
        """
        transactions = self.__paged_request(f'ticket/{ticket_id}/history', params={'fields': 'Type,Creator,Created,Description',
                                                                                   'fields[Creator]': 'id,Name,RealName,EmailAddress'
                                                                                   }
                                            )

        return list(transactions)

    def get_transaction(self, transaction_id: typing.Union[str, int]) -> typing.Dict[str, typing.Any]:
        """Get a transaction

        :param transaction_id: ID of transaction
        :returns: List of history items ordered increasingly by time of event.
                  Each history item is a tuple containing (id, Description).
                  Returns None if ticket does not exist.
        """
        return self.__request(f'transaction/{transaction_id}', get_params={'fields': 'Description'})

    def __correspond(self,
                     ticket_id: typing.Union[str, int],
                     content: str = '',
                     action: str = 'correspond',
                     content_type: str = 'text/plain',
                     attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                     ) -> typing.List[str]:
        """ Sends out the correspondence

        :param ticket_id: ID of ticket to which message belongs
        :keyword content: Content of email message
        :keyword action: correspond or comment
        :keyword content_type: Content type of email message, default to text/plain
        :keyword attachments: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :returns: List of messages returned by the backend related to the executed action.
        :raises BadRequest: When ticket does not exist
        """
        if action not in ('correspond', 'comment'):  # pragma: no cover
            raise InvalidUse('action must be either "correspond" or "comment"')

        post_data: typing.Dict[str, typing.Any] = {'Content': content,
                                                   'ContentType': content_type,
                                                   }

        # Adding a one-shot cc/bcc is not supported by RT5.0.2
        # if cc:
        #     post_data['Cc'] = cc
        #
        # if bcc:
        #     post_data['Bcc'] = bcc

        if attachments:
            post_data['Attachments'] = [attachment.to_dict() for attachment in attachments]

        msg = self.__request(f'ticket/{ticket_id}/{action}', json_data=post_data)

        if not isinstance(msg, list):  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        self.logger.debug(msg)

        return msg

    def reply(self,
              ticket_id: typing.Union[str, int],
              content: str = '',
              content_type: str = 'text/plain',
              attachments: typing.Optional[typing.Sequence[Attachment]] = None,
              ) -> bool:
        """ Sends email message to the contacts in ``Requestors`` field of
        given ticket with subject as is set in ``Subject`` field.

        :param ticket_id: ID of ticket to which message belongs
        :keyword content: Content of email message
        :keyword content_type: Content type of email message, default to text/plain
        :keyword attachments: Optional list of Attachment objects
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequest: When ticket does not exist
        """
        msg = self.__correspond(ticket_id, content, 'correspond', content_type, attachments)

        if not (isinstance(msg, list) and len(msg) >= 1):  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        return bool(msg[0])

    def comment(self,
                ticket_id: typing.Union[str, int],
                content: str = '',
                content_type: str = 'text/plain',
                attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                ) -> bool:
        """ Adds comment to the given ticket.

        :param ticket_id: ID of ticket to which comment belongs
        :keyword content: Content of comment
        :keyword content_type: Content type of comment, default to text/plain
        :keyword attachments: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequest: When ticket does not exist
        """
        msg = self.__correspond(ticket_id, content, 'comment', content_type, attachments)

        if not (isinstance(msg, list) and len(msg) >= 1):  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        return bool(msg[0])

    def get_attachments(self, ticket_id: typing.Union[str, int]) -> typing.Sequence[typing.Dict[str, str]]:
        """ Get attachment list for a given ticket

        :param ticket_id: ID of ticket
        :returns: List of tuples for attachments belonging to given ticket.
                  Tuple format: (id, name, content_type, size)
                  Returns None if ticket does not exist.
        """
        attachments = []

        for item in self.__paged_request(f'ticket/{ticket_id}/attachments',
                                         json_data=[{"field": "Filename", "operator": "IS NOT", "value": ""}],
                                         params={'fields': 'Filename,ContentType,ContentLength'}):
            attachments.append(item)

        return attachments

    def get_attachments_ids(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[int]]:
        """ Get IDs of attachments for given ticket.

        :param ticket_id: ID of ticket
        :returns: List of IDs (type int) of attachments belonging to given
                  ticket. Returns None if ticket does not exist.
        """
        attachments = []

        for item in self.__paged_request(f'ticket/{ticket_id}/attachments',
                                         json_data=[{"field": "Filename", "operator": "IS NOT", "value": ""}]
                                         ):
            attachments.append(int(item['id']))

        return attachments

    def get_attachment(self, attachment_id: typing.Union[str, int]) -> typing.Optional[dict]:
        """ Get attachment.

        :param ticket_id: ID of ticket
        :param attachment_id: ID of attachment for obtain
        :returns: Attachment as dictionary with these keys:

                      * Transaction
                      * ContentType
                      * Parent
                      * Creator
                      * Created
                      * Filename
                      * Content (bytes type)
                      * Headers
                      * MessageId
                      * ContentEncoding
                      * id
                      * Subject

                  All these fields are strings, just 'Headers' holds another
                  dictionary with attachment headers as strings e.g.:

                      * Delivered-To
                      * From
                      * Return-Path
                      * Content-Length
                      * To
                      * X-Seznam-User
                      * X-QM-Mark
                      * Domainkey-Signature
                      * RT-Message-ID
                      * X-RT-Incoming-Encryption
                      * X-Original-To
                      * Message-ID
                      * X-Spam-Status
                      * In-Reply-To
                      * Date
                      * Received
                      * X-Country
                      * X-Spam-Checker-Version
                      * X-Abuse
                      * MIME-Version
                      * Content-Type
                      * Subject

                  .. warning:: Content-Length parameter is set after opening
                               ticket in web interface!

                  Set of headers available depends on mailservers sending
                  emails not on Request Tracker!

                  Returns None if ticket or attachment does not exist.
        :raises UnexpectedMessageFormat: Unexpected format of returned message.
        """
        return self.__request(f'attachment/{attachment_id}')

    def get_user(self, user_id: typing.Union[int, str]) -> typing.Dict[str, typing.Any]:
        """ Get user details.

        :param user_id: Identification of user by username (str) or user ID
                        (int)
        :returns: User details as strings in dictionary with these keys for RT
                  users:

                      * Lang
                      * RealName
                      * Privileged
                      * Disabled
                      * Gecos
                      * EmailAddress
                      * Password
                      * id
                      * Name

                  Or these keys for external users (e.g. Requestors replying
                  to email from RT:

                      * RealName
                      * Disabled
                      * EmailAddress
                      * Password
                      * id
                      * Name

        :raises UnexpectedMessageFormat: In case that returned status code is not 200
        :raises NotFoundError: If the user does not exist.
        """
        return self.__request(f'user/{user_id}')

    def user_exists(self, user_id: typing.Union[int, str], privileged: bool = True) -> bool:
        """Check if a given user_id exists.

        :parameter user_id: User ID to lookup.
        :parameter privileged: If set to True, only return True if the user_id was found and is privileged.

        :returns: bool: True on success, else False.
        """
        try:
            user_dict = self.get_user(user_id)

            if not privileged or (privileged and user_dict.get('Privileged', '0') == 1):
                return True
        except rt.exceptions.NotFoundError:
            return False

        return False

    def create_user(self, Name: str, EmailAddress: str, **kwargs: typing.Any) -> str:
        """ Create user.

        :param Name: User name (login for privileged, required)
        :param EmailAddress: Email address (required)
        :param kwargs: Optional fields to set (see edit_user)
        :returns: ID of new user or False when create fails
        :raises BadRequest: When user already exists
        :raises InvalidUse: When invalid fields are set
        """
        valid_fields = {'Name', 'Password', 'EmailAddress', 'RealName',
                        'Nickname', 'Gecos', 'Organization', 'Address1', 'Address2',
                        'City', 'State', 'Zip', 'Country', 'HomePhone', 'WorkPhone',
                        'MobilePhone', 'PagerPhone', 'ContactInfo', 'Comments',
                        'Signature', 'Lang', 'EmailEncoding', 'WebEncoding',
                        'ExternalContactInfoId', 'ContactInfoSystem', 'ExternalAuthId',
                        'AuthSystem', 'Privileged', 'Disabled'}
        invalid_fields = []

        post_data = {'Name': Name,
                     'EmailAddress': EmailAddress
                     }

        for k, v in kwargs.items():
            if k not in valid_fields:
                invalid_fields.append(k)

            else:
                post_data[k] = v

        if invalid_fields:
            raise InvalidUse(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request('user', json_data=post_data)
        except UnexpectedResponse as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            raise

        return ret['id']

    def edit_user(self, user_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.List[str]:
        """ Edit user profile (undocumented API feature).

        :param user_id: Identification of user by username (str) or user ID
                        (int)
        :param kwargs: Other fields to edit from the following list:

                          * Name
                          * Password
                          * EmailAddress
                          * RealName
                          * NickName
                          * Gecos
                          * Organization
                          * Address1
                          * Address2
                          * City
                          * State
                          * Zip
                          * Country
                          * HomePhone
                          * WorkPhone
                          * MobilePhone
                          * PagerPhone
                          * ContactInfo
                          * Comments
                          * Signature
                          * Lang
                          * EmailEncoding
                          * WebEncoding
                          * ExternalContactInfoId
                          * ContactInfoSystem
                          * ExternalAuthId
                          * AuthSystem
                          * Privileged
                          * Disabled

        :returns: List of status messages
        :raises BadRequest: When user does not exist
        :raises InvalidUse: When invalid fields are set
        """
        valid_fields = {'Name', 'Password', 'EmailAddress', 'RealName',
                        'Nickname', 'Gecos', 'Organization', 'Address1', 'Address2',
                        'City', 'State', 'Zip', 'Country', 'HomePhone', 'WorkPhone',
                        'MobilePhone', 'PagerPhone', 'ContactInfo', 'Comments',
                        'Signature', 'Lang', 'EmailEncoding', 'WebEncoding',
                        'ExternalContactInfoId', 'ContactInfoSystem', 'ExternalAuthId',
                        'AuthSystem', 'Privileged', 'Disabled'}
        invalid_fields = []

        post_data = {}

        for key, val in kwargs.items():
            if key not in valid_fields:
                invalid_fields.append(key)

            else:
                post_data[key] = val

        if invalid_fields:
            raise InvalidUse(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request_put(f'user/{user_id}', json_data=post_data)
        except UnexpectedResponse as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            raise

        return ret

    def delete_user(self, user_id: typing.Union[str, int]) -> None:
        """ Disable a user.

        :param user_id: Identification of a user by name (str) or ID (int)

        :raises BadRequest: When user does not exist
        :raises NotFoundError: If the user does not exist
        """
        try:
            _ = self.__request_delete(f'user/{user_id}')
        except UnexpectedResponse as exc:
            if exc.status_code == 400:  # pragma: no cover
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            if exc.status_code == 204:
                return

            raise  # pragma: no cover

    def get_queue(self, queue_id: typing.Union[str, int]) -> typing.Optional[typing.Dict[str, typing.Any]]:
        """ Get queue details.

        :param queue_id: Identification of queue by name (str) or queue ID
                         (int)
        :returns: Queue details as strings in dictionary with these keys
                  if queue exists:

                      * id
                      * Name
                      * Description
                      * CorrespondAddress
                      * CommentAddress
                      * InitialPriority
                      * FinalPriority
                      * DefaultDueIn

        :raises UnexpectedMessageFormat: In case that returned status code is not 200
        :raises NotFoundError: In case the queue does not exist
        """
        return self.__request(f'queue/{queue_id}')

    def get_all_queues(self, include_disabled: bool = False) -> typing.List[typing.Dict[str, typing.Any]]:
        """ Return a list of all queues.

        :param include_disabled: Set to True to also return disabled queues.

        :returns: Queue details as strings in dictionary with these keys
                  if queue exists (otherwise None):

                      * id
                      * Name
                      * Description
                      * CorrespondAddress
                      * CommentAddress
                      * InitialPriority
                      * FinalPriority
                      * DefaultDueIn

        :raises UnexpectedMessageFormat: In case that returned status code is not 200
        """
        params = {'fields': 'Name,Description', 'find_disabled_rows': int(include_disabled)}
        queues = self.__paged_request('queues/all', params=params)

        return list(queues)

    def edit_queue(self, queue_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.List[str]:
        """ Edit queue (undocumented API feature).

        :param queue_id: Identification of queue by name (str) or ID (int)
        :param kwargs: Other fields to edit from the following list:

                          * Name
                          * Description
                          * CorrespondAddress
                          * CommentAddress
                          * Disabled
                          * SLADisabled
                          * Lifecycle
                          * SortOrder

        :returns: List of status messages
        :raises BadRequest: When queue does not exist
        :raises InvalidUse: When invalid fields are set
        """
        valid_fields = {'Name', 'Description', 'CorrespondAddress', 'CommentAddress',
                        'Disabled', 'SLADisabled', 'Lifecycle', 'SortOrder'
                        }
        invalid_fields = []

        post_data = {}

        for key, val in kwargs.items():
            if key not in valid_fields:
                invalid_fields.append(key)

            else:
                post_data[key] = val

        if invalid_fields:
            raise InvalidUse(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request_put(f'queue/{queue_id}', json_data=post_data)
        except UnexpectedResponse as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            raise

        return ret

    def create_queue(self, Name: str, **kwargs: typing.Any) -> int:
        """ Create queue (undocumented API feature).

        :param Name: Queue name (required)
        :param kwargs: Optional fields to set (see edit_queue)
        :returns: ID of new queue or False when create fails
        :raises BadRequest: When queue already exists
        :raises InvalidUse: When invalid fields are set
        """
        valid_fields = {'Name', 'Description', 'CorrespondAddress', 'CommentAddress',
                        'Disabled', 'SLADisabled', 'Lifecycle', 'SortOrder'
                        }
        invalid_fields = []

        post_data = {'Name': Name}

        for key, val in kwargs.items():
            if key not in valid_fields:
                invalid_fields.append(key)

            else:
                post_data[key] = val

        if invalid_fields:
            raise InvalidUse(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request('queue', json_data=post_data)
        except UnexpectedResponse as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            raise

        return int(ret['id'])

    def delete_queue(self, queue_id: typing.Union[str, int]) -> None:
        """ Disable a queue.

        :param queue_id: Identification of queue by name (str) or ID (int)

        :returns: ID or name of edited queue or False when edit fails
        :raises BadRequest: When queue does not exist
        :raises NotFoundError: If the queue does not exist
        """
        try:
            _ = self.__request_delete(f'queue/{queue_id}')
        except UnexpectedResponse as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequest(exc.response_message) from exc

            if exc.status_code == 204:
                return

            raise  # pragma: no cover

    def get_links(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Dict[str, str]]]:
        """ Gets the ticket links for a single ticket.

        :param ticket_id: ticket ID
        :returns: Links as lists of strings in dictionary with these keys
                  (just those which are defined):

                        * depends-on
                        * depended-on-by
                        * parent
                        * child
                        * refers-to
                        * referred-to-by

                  None is returned if ticket does not exist.
        :raises UnexpectedMessageFormat: In case that returned status code is not 200
        """
        ticket = self.get_ticket(ticket_id)

        links = [link for link in ticket['_hyperlinks'] if link.get('type', '') == 'ticket' and link['ref'] != 'self']

        return links

    def edit_link(self, ticket_id: typing.Union[str, int], link_name: str, link_value: typing.Union[str, int],
                  delete: bool = False) -> bool:
        """ Creates or deletes a link between the specified tickets (undocumented API feature).

        :param ticket_id: ID of ticket to edit
        :param link_name: Name of link to edit (DependsOn, DependedOnBy,
                          RefersTo, ReferredToBy, HasMember or MemberOf)
        :param link_value: Either ticker ID or external link.
        :param delete: if True the link is deleted instead of created
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Ticket with given ID does not exist or link to delete is
                      not found
        :raises InvalidUse: When none or more then one links are specified. Also
                            when wrong link name is used.
        """
        if link_name not in VALID_TICKET_LINK_NAMES:
            raise InvalidUse(f'Unsupported link name. Use one of "{", ".join(VALID_TICKET_LINK_NAMES)}".')

        if delete:
            json_data = {f'Delete{link_name}': link_value}
        else:
            json_data = {f'Add{link_name}': link_value}

        msg = self.__request_put(f'ticket/{ticket_id}', json_data=json_data)

        if msg and isinstance(msg, list) and msg[0].startswith('Couldn\'t resolve'):
            raise NotFoundError(msg[0])

        return True

    def merge_ticket(self, ticket_id: typing.Union[str, int], into_id: typing.Union[str, int]) -> bool:
        """ Merge ticket into another (undocumented API feature).

        :param ticket_id: ID of ticket to be merged
        :param into_id: ID of destination ticket
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either origin or destination ticket does not
                      exist or user does not have ModifyTicket permission.
        """
        msg = self.__request_put(f'ticket/{ticket_id}', json_data={'MergeInto': into_id})

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        self.logger.debug(str(msg))

        return msg[0].lower() == 'merge successful'

    def take(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Take ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      have TakeTicket permission.
        """
        msg = self.__request_put(f'ticket/{ticket_id}/take')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        self.logger.debug(str(msg))

        return msg[0].lower().startswith('owner changed')

    def untake(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Untake ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      own the ticket.
        """
        msg = self.__request_put(f'ticket/{ticket_id}/untake')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        self.logger.debug(str(msg))

        return msg[0].lower().startswith('owner changed')

    def steal(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Steal ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      have StealTicket permission.
        """
        msg = self.__request_put(f'ticket/{ticket_id}/steal')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponse(str(msg))

        self.logger.debug(str(msg))

        return msg[0].lower().startswith('owner changed')
