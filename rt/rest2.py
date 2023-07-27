"""Python interface to Request Tracker :term:`API`

Description of Request Tracker :term:`REST` :term:`API`:
https://docs.bestpractical.com/rt/5.0.2/RT/REST2.html
"""

import base64
import dataclasses
import datetime
import json
import logging
import re
import sys
import typing
from urllib.parse import urljoin

import requests
import requests.auth
import requests_toolbelt

import rt.exceptions
from .exceptions import AuthorizationError, UnexpectedResponseError, NotFoundError, InvalidUseError

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

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
TYPE_VALID_TICKET_LINK_NAMES = Literal['Parent', 'Child', 'RefersTo',
                                       'ReferredToBy', 'DependsOn', 'DependedOnBy']
TYPE_CONTENT_TYPE = Literal['text/plain', 'text/html']

REGEX_PATTERNS = {'does_not_exist': re.compile(r'''(user|queue|resource)(?: [^does]+)? does not exist''', re.I)}


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

    def multipart_form_element(self) -> typing.Tuple[str, bytes, str]:
        """Convert to a tuple as required for multipart-form-data submission."""
        return (self.file_name,
                self.file_content,
                self.file_type,
                )


class Rt:
    r""" :term:`API` for Request Tracker according to
    https://docs.bestpractical.com/rt/5.0.2/RT/REST2.html. Interface is based on
    :term:`REST` architecture, which is based on HTTP/1.1 protocol. This module
    is therefore mainly sending and parsing special HTTP messages.

    .. warning:: You need at least version 5.0.2 of RT.

    .. note:: Use only ASCII LF as newline (``\\n``). Time is returned in UTC.
              All strings returned are encoded in UTF-8 and the same is
              expected as input for string values.
    """

    def __init__(self,
                 url: str,
                 proxy: typing.Optional[str] = None,
                 verify_cert: typing.Optional[typing.Union[str, bool]] = True,
                 http_auth: typing.Optional[requests.auth.AuthBase] = None,
                 token: typing.Optional[str] = None,
                 http_timeout: typing.Optional[int] = 20,
                 ) -> None:
        """ API initialization.

        :param url: Base URL for Request Tracker API.
                      E.g.: http://tracker.example.com/REST/2.0/
        :param proxy: Proxy server (string with http://user:password@host/ syntax)
        :param http_auth: Specify a http authentication instance, e.g. HTTPBasicAuth(), HTTPDigestAuth(),
                            etc. to be used for authenticating to RT
        :param token: Optional authentication token to be used instead of basic authentication.
        :param http_timeout: HTTP timeout after which a request is aborted.

        :raises ValueError: If the specified `url` is invalid.
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
        """Output debug information for a given HTTP response."""
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
                  attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                  ) -> typing.Union[typing.Dict[str, typing.Any], typing.List[str]]:
        """ General request for :term:`API`.

        :param selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :param get_params: Parameters to add for a GET request.
        :param json_data: JSON request to send to the API.
        :param post_data: Dictionary with POST method fields
        :param attachments: Optional list of :py:class:`~rt.rest2.Attachment` objects

        :returns: dict or list depending on request
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        try:
            url = str(urljoin(self.url, selector))
            if not attachments:
                if json_data:
                    response = self.session.post(url, json=json_data, timeout=self.http_timeout)
                elif post_data:
                    response = self.session.post(url, data=post_data, timeout=self.http_timeout)
                else:
                    response = self.session.get(url, params=get_params, timeout=self.http_timeout)
            else:
                fields: typing.List[typing.Tuple[str, typing.Any]] = [('Attachments', attachment.multipart_form_element()) for attachment in attachments]
                fields.append(('JSON', json.dumps(json_data)))

                multipart_data = requests_toolbelt.MultipartEncoder(fields=fields)

                _headers = dict(self.session.headers)
                _headers['content-type'] = multipart_data.content_type

                response = self.session.post(url, data=multipart_data, headers=_headers, timeout=self.http_timeout)

            self.__debug_response(response)
            self.__check_response(response)

            try:
                result = response.json()
            except LookupError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'Unknown response encoding: {response.encoding}.') from exc
            except UnicodeError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''') from exc

            return result
        except requests.exceptions.ConnectionError as exc:  # pragma: no cover
            raise ConnectionError("Connection error", exc) from exc

    def __request_put(self,
                      selector: str,
                      json_data: typing.Optional[typing.Dict[str, typing.Any]] = None
                      ) -> typing.List[str]:
        """ PUT request for :term:`API`.

        :param selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :param json_data: JSON request to send to the API.
        :returns: list
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
            except LookupError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'Unknown response encoding: {response.encoding}.') from exc
            except UnicodeError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''') from exc

            return result
        except requests.exceptions.ConnectionError as exc:  # pragma: no cover
            raise ConnectionError("Connection error", exc) from exc

    def __request_delete(self,
                         selector: str,
                         ) -> typing.Dict[str, str]:
        """ DELETE request for :term:`API`.

        :param selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``

        :returns: dict
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
            except LookupError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'Unknown response encoding: {response.encoding}.') from exc
            except UnicodeError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'''Unknown response encoding (UTF-8 does not work) - "{response.content.decode('utf-8', 'replace')}".''') from exc

            return result
        except requests.exceptions.ConnectionError as exc:  # pragma: no cover
            raise ConnectionError("Connection error", exc) from exc

    def __paged_request(self,
                        selector: str,
                        json_data: typing.Optional[typing.Union[typing.List[typing.Dict[str, typing.Any]], typing.Dict[str, typing.Any]]] = None,
                        params: typing.Optional[typing.Dict[str, typing.Any]] = None,
                        page: int = 1,
                        per_page: int = 20,
                        recurse: bool = True
                        ) -> typing.Iterator[typing.Dict[str, typing.Any]]:
        """ Request using pagination for :term:`API`.

        :param selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :param json_data: JSON request to send to the API.
        :param page: The page number to get.
        :param per_page: Number of results per page to get.
        :param recurse: Set on the initial call in order to retrieve all pages recursively.

        :returns: dict
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
            except LookupError as exc:  # pragma: no cover
                raise UnexpectedResponseError(f'Unknown response encoding: {response.encoding}.') from exc
            except UnicodeError:  # pragma: no cover
                # replace errors - we need decoded content just to check for error codes in __check_response
                result = response.content.decode('utf-8', 'replace')

            if not isinstance(result, dict) and 'items' in result:
                raise UnexpectedResponseError('Server returned an unexpected result')

            yield from result['items']

            if recurse and result['pages'] > result['page']:
                for _page in range(2, result['pages'] + 1):
                    yield from self.__paged_request(selector, json_data=json_data, page=_page,
                                                    per_page=result['per_page'], params=params, recurse=False)

        except requests.exceptions.ConnectionError as exc:  # pragma: no cover
            raise ConnectionError("Connection error", exc) from exc

    @staticmethod
    def __check_response(response: requests.Response) -> None:
        """ Search general errors in server response and raise exceptions when found.

        :param response: Response from HTTP request.
        :raises BadRequestError: If the server returned an HTTP/400 error.
        :raises AuthorizationError: Credentials are invalid or missing.
        :raises NotFoundError: Resource was not found.
        :raises UnexpectedResponseError: Server returned an unexpected status code.
        """
        if response.status_code == 400:  # pragma: no cover
            try:
                ret = response.json()
            except json.JSONDecodeError:
                ret = 'Bad request'

            if isinstance(ret, dict):
                raise rt.exceptions.BadRequestError(ret['message'])

            raise rt.exceptions.BadRequestError(ret)

        if response.status_code == 401:  # pragma: no cover
            raise AuthorizationError(
                'Server could not verify that you are authorized to access the requested document.')
        if response.status_code == 404:
            raise NotFoundError('No such resource found.')
        if response.status_code not in (200, 201):
            raise UnexpectedResponseError(f'Received status code {response.status_code} instead of 200.',
                                          status_code=response.status_code,
                                          response_message=response.text)

    def __get_url(self, url: str) -> typing.Dict[str, typing.Any]:
        """Call a URL as specified in the returned JSON of an API operation."""
        url_ = url.split('/REST/2.0/', 1)[1]
        res = self.__request(url_)

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

    def new_correspondence(self, queue: typing.Optional[typing.Union[str, object]] = None) -> typing.Iterator[dict]:
        """ Obtains tickets changed by other users than the system one.

        :param queue: Queue where to search

        :returns: Iterator of tickets which were last updated by another user than
                  the system one, ordered in decreasing order by LastUpdated.
                  Each ticket is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        return self.search(queue=queue, order='-LastUpdated')

    def last_updated(self, since: str, queue: typing.Optional[str] = None) -> typing.Iterator[dict]:
        """ Obtains tickets changed after given date.

        :param since: Date as string in form '2011-02-24'
        :param queue: Queue where to search

        :returns: Iterator of tickets with LastUpdated parameter later than
                  *since* ordered in decreasing order by LastUpdated.
                  Each ticket is a dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.

        :raises InvalidUseError: If the specified date is of an unsupported format.
        """
        if not self.__validate_date(since):
            raise InvalidUseError(f'Invalid date specified - "{since}"')

        return self.search(queue=queue, order='-LastUpdated',
                           LastUpdated__gt=since)

    @classmethod
    def __validate_date(cls, _date: str) -> bool:
        """Check whether the specified date is in the supported format."""
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

    def search(self, queue: typing.Optional[typing.Union[str, object]] = None, order: typing.Optional[str] = None,
               raw_query: typing.Optional[str] = None, query_format: str = 'l', **kwargs: typing.Any) -> typing.Iterator[dict]:
        r""" Search arbitrary needles in given fields and queue.

        Example::

            >>> tracker = Rt('http://tracker.example.com/REST/2.0/', 'rt-username', 'top-secret')
            >>> tickets = list(tracker.search(CF_Domain='example.com', Subject__like='warning'))
            >>> tickets = list(tracker.search(queue='General', order='Status', raw_query="id='1'+OR+id='2'+OR+id='3'"))

        :param queue:      Queue where to search. If you wish to search across
                           all of your queues, pass the ALL_QUEUES object as the
                           argument.
        :param order:      Name of field sorting result list, for descending
                           order put - before the field name. E.g. -Created
                           will put the newest tickets at the beginning
        :param raw_query:  A raw query to provide to RT if you know what
                             you are doing. You may still pass Queue and order
                             kwargs, so use these instead of including them in
                             the raw query. You can refer to the RT query builder.
                             If passing raw_query, all other \*\*kwargs will be ignored.
        :param query_format: Format of the query:

                               - i: only *id* fields are populated
                               - s: only *id* and *subject* fields are populated
                               - l: multi-line format, all fields are populated
        :param kwargs:     Other arguments possible to set if not passing raw_query:

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

        :returns: Iterator over matching tickets. Each ticket is the same dictionary
                  as in :py:meth:`~Rt.get_ticket`.
        :raises:  UnexpectedMessageFormatError: Unexpected format of returned message.
                  InvalidQueryError: If raw query is malformed
        """
        get_params = {}
        query = []
        url = 'tickets'

        if queue is not None:
            query.append(f'Queue=\'{queue}\'')
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
                    query.append(f'''CF.{{{key[3:]}}}'{op}'{value}\'''')
        else:
            query.append(raw_query)
        get_params['query'] = ' AND '.join('(' + part + ')' for part in query)
        if order:
            if order.startswith("-"):
                get_params['orderby'] = order[1:]
                get_params['order'] = "DESC"
            else:
                get_params['orderby'] = order

        if query_format == 'l':
            get_params['fields'] = 'Owner,Status,Created,Subject,Queue,CustomFields,Requestor,Cc,AdminCc,Started,Created,TimeEstimated,Due,Type,InitialPriority,Priority,TimeLeft,LastUpdated'
            get_params['fields[Queue]'] = 'Name'
        elif query_format == 's':
            get_params['fields'] = 'Subject'

        yield from self.__paged_request(url, params=get_params)

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
        :raises UnexpectedMessageFormatError: Unexpected format of returned message.
        :raises NotFoundError: If there is no ticket with the specified ticket_id.
        """
        res = self.__request(f'ticket/{ticket_id}', get_params={'fields[Queue]': 'Name'})

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

    def create_ticket(self,
                      queue: str,
                      content_type: TYPE_CONTENT_TYPE = 'text/plain',
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

        :param queue: Queue where to create ticket
        :param content_type: Content-type of the Content parameter; can be either text/plain or text/html.
        :param subject: Optional subject for the ticket.
        :param content: Optional content of the ticket. Must be specified unless attachments are specified.
        :param attachments: Optional list of :py:class:`~rt.rest2.Attachment` objects
        :param kwargs: Other arguments possible to set:

                         Requestors, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due

        :returns: ID of new ticket
        :raises ValueError: If the `content_type` is not of a supported format.
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

        res = self.__request('ticket', json_data=ticket_data, attachments=attachments)

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return int(res['id'])

    def edit_ticket(self, ticket_id: typing.Union[str, int], **kwargs: typing.Any) -> bool:
        """ Edit ticket values.

        :param ticket_id: ID of ticket to edit
        :param kwargs: Other arguments possible to set:

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

        if not isinstance(msg, list):  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

        if not msg:
            return True

        for k in msg:
            if REGEX_PATTERNS['does_not_exist'].search(k):
                raise rt.exceptions.NotFoundError(k)

        return bool(msg[0])

    def get_ticket_history(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Dict[str, typing.Any]]]:
        """ Get set of short history items

        :param ticket_id: ID of ticket
        :returns: List of history items ordered increasingly by time of event.
                  Each history item is a tuple containing (id, Description).
                  Returns None if ticket does not exist.
        """
        transactions = self.__paged_request(f'ticket/{ticket_id}/history', params={'fields': 'Type,Creator,Created,Description,_hyperlinks',
                                                                                   'fields[Creator]': 'id,Name,RealName,EmailAddress'
                                                                                   }
                                            )

        return list(transactions)

    def get_transaction(self, transaction_id: typing.Union[str, int]) -> typing.Dict[str, typing.Any]:
        """Get a transaction

        :param transaction_id: ID of transaction
        :returns: Return a single transaction.
        """
        res = self.__request(f'transaction/{transaction_id}', get_params={'fields': 'Description'})

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

    def __correspond(self,
                     ticket_id: typing.Union[str, int],
                     content: str = '',
                     action: Literal['correspond', 'comment'] = 'correspond',
                     content_type: TYPE_CONTENT_TYPE = 'text/plain',
                     attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                     ) -> typing.List[str]:
        """ Sends out the correspondence

        :param ticket_id: ID of ticket to which message belongs
        :param content: Content of email message
        :param action: correspond or comment
        :param content_type: Content type of email message, defaults to text/plain. Alternative is text/html.
        :param attachments: Optional list of :py:class:`~rt.rest2.Attachment` objects
        :returns: List of messages returned by the backend related to the executed action.
        :raises BadRequestError: When ticket does not exist
        :raises InvalidUseError: If the `action` parameter is invalid
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        if action not in ('correspond', 'comment'):  # pragma: no cover
            raise InvalidUseError('action must be either "correspond" or "comment"')

        post_data: typing.Dict[str, typing.Any] = {'Content': content,
                                                   'ContentType': content_type,
                                                   }

        # Adding a one-shot cc/bcc is not supported by RT5.0.2
        # if cc:
        #     post_data['Cc'] = cc
        #
        # if bcc:
        #     post_data['Bcc'] = bcc

        res = self.__request(f'ticket/{ticket_id}/{action}', json_data=post_data, attachments=attachments)

        if not isinstance(res, list):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        self.logger.debug(res)

        return res

    def reply(self,
              ticket_id: typing.Union[str, int],
              content: str = '',
              content_type: TYPE_CONTENT_TYPE = 'text/plain',
              attachments: typing.Optional[typing.Sequence[Attachment]] = None,
              ) -> bool:
        """ Sends email message to the contacts in ``Requestors`` field of
        given ticket with subject as is set in ``Subject`` field.

        :param ticket_id: ID of ticket to which message belongs
        :param content: Content of email message (text/plain or text/html)
        :param content_type: Content type of email message, default to text/plain
        :param attachments: Optional list of :py:class:`~rt.rest2.Attachment` objects
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequestError: When ticket does not exist
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__correspond(ticket_id, content, 'correspond', content_type, attachments)

        if not (isinstance(msg, list) and len(msg) >= 1):  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

        return bool(msg[0])

    def delete_ticket(self, ticket_id: typing.Union[str, int]) -> None:
        """ Mark a ticket as deleted.

        :param ticket_id: ID of ticket

        :raises BadRequestError: When user does not exist
        :raises NotFoundError: If the user does not exist
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        try:
            self.__request_delete(f'ticket/{ticket_id}')
        except UnexpectedResponseError as exc:
            if exc.status_code == 400:  # pragma: no cover
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            if exc.status_code == 204:
                return

            raise  # pragma: no cover

    def comment(self,
                ticket_id: typing.Union[str, int],
                content: str = '',
                content_type: TYPE_CONTENT_TYPE = 'text/plain',
                attachments: typing.Optional[typing.Sequence[Attachment]] = None,
                ) -> bool:
        """ Adds comment to the given ticket.

        :param ticket_id: ID of ticket to which comment belongs
        :param content: Content of comment
        :param content_type: Content type of comment, default to text/plain
        :param attachments: Optional list of :py:class:`~rt.rest2.Attachment` objects
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequestError: When ticket does not exist
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__correspond(ticket_id, content, 'comment', content_type, attachments)

        if not (isinstance(msg, list) and len(msg) >= 1):  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

        return bool(msg[0])

    def get_attachments(self, ticket_id: typing.Union[str, int]) -> typing.Sequence[typing.Dict[str, str]]:
        """ Get attachment list for a given ticket

        Example of a return result:

        .. code-block:: json

            [
                {
                    "id": "17",
                    "Filename": "README.rst",
                    "ContentLength": "3578",
                    "type": "attachment",
                    "ContentType": "test/plain",
                    "_url": "http://localhost:8080/REST/2.0/attachment/17"
                }
            ]

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

        :param attachment_id: ID of attachment to fetch
        :returns: Attachment as dictionary with these keys:

                      * Transaction
                      * ContentType
                      * Parent
                      * Creator
                      * Created
                      * Filename
                      * Content (base64 encoded string)
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

                  Set of headers available depends on mailservers sending
                  emails not on Request Tracker!

        :raises UnexpectedMessageFormatError: Unexpected format of returned message.
        :raises NotFoundError: If attachment with specified ID does not exist.
        """
        res = self.__request(f'attachment/{attachment_id}')

        if not (res is None or isinstance(res, dict)):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

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

                  Or these keys for external users (e.g. Requestors) replying
                  to email from RT:

                      * RealName
                      * Disabled
                      * EmailAddress
                      * Password
                      * id
                      * Name

        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        :raises NotFoundError: If the user does not exist.
        """
        res = self.__request(f'user/{user_id}')

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

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

    def create_user(self, user_name: str, email_address: str, **kwargs: typing.Any) -> str:
        """ Create user.

        :param user_name: Username (login for privileged, required)
        :param email_address: Email address (required)
        :param kwargs: Optional fields to set (see edit_user)
        :returns: ID of new user or False when create fails
        :raises BadRequestError: When user already exists
        :raises InvalidUseError: When invalid fields are set
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        valid_fields = {'Name', 'Password', 'EmailAddress', 'RealName',
                        'Nickname', 'Gecos', 'Organization', 'Address1', 'Address2',
                        'City', 'State', 'Zip', 'Country', 'HomePhone', 'WorkPhone',
                        'MobilePhone', 'PagerPhone', 'ContactInfo', 'Comments',
                        'Signature', 'Lang', 'EmailEncoding', 'WebEncoding',
                        'ExternalContactInfoId', 'ContactInfoSystem', 'ExternalAuthId',
                        'AuthSystem', 'Privileged', 'Disabled', 'CustomFields'}
        invalid_fields = []

        post_data = {'Name': user_name,
                     'EmailAddress': email_address
                     }

        for k, v in kwargs.items():
            if k not in valid_fields:
                invalid_fields.append(k)

            else:
                post_data[k] = v

        if invalid_fields:
            raise InvalidUseError(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            res = self.__request('user', json_data=post_data)
        except UnexpectedResponseError as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            raise

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res['id']

    def edit_user(self, user_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.List[str]:
        """ Edit user profile.

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
        :raises BadRequestError: When user does not exist
        :raises InvalidUseError: When invalid fields are set
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        valid_fields = {'Name', 'Password', 'EmailAddress', 'RealName',
                        'Nickname', 'Gecos', 'Organization', 'Address1', 'Address2',
                        'City', 'State', 'Zip', 'Country', 'HomePhone', 'WorkPhone',
                        'MobilePhone', 'PagerPhone', 'ContactInfo', 'Comments',
                        'Signature', 'Lang', 'EmailEncoding', 'WebEncoding',
                        'ExternalContactInfoId', 'ContactInfoSystem', 'ExternalAuthId',
                        'AuthSystem', 'Privileged', 'Disabled', 'CustomFields'}
        invalid_fields = []

        post_data = {}

        for key, val in kwargs.items():
            if key not in valid_fields:
                invalid_fields.append(key)

            else:
                post_data[key] = val

        if invalid_fields:
            raise InvalidUseError(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request_put(f'user/{user_id}', json_data=post_data)
        except UnexpectedResponseError as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            raise

        return ret

    def delete_user(self, user_id: typing.Union[str, int]) -> None:
        """ Disable a user.

        :param user_id: Identification of a user by name (str) or ID (int)

        :raises BadRequestError: When user does not exist
        :raises NotFoundError: If the user does not exist
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        try:
            _ = self.__request_delete(f'user/{user_id}')
        except UnexpectedResponseError as exc:
            if exc.status_code == 400:  # pragma: no cover
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            if exc.status_code == 204:
                return

            raise  # pragma: no cover

    def get_queue(self, queue_id: typing.Union[str, int]) -> typing.Optional[typing.Dict[str, typing.Any]]:
        """ Get queue details.

        Example of a return result:

        .. code-block:: json

            {
                "LastUpdatedBy": {
                    "_url": "http://localhost:8080/REST/2.0/user/RT_System",
                    "type": "user",
                    "id": "RT_System"
                },
                "LastUpdated": "2022-03-06T04:53:38Z",
                "AdminCc": [],
                "SortOrder": "0",
                "CorrespondAddress": "",
                "Creator": {
                    "id": "RT_System",
                    "_url": "http://localhost:8080/REST/2.0/user/RT_System",
                    "type": "user"
                },
                "Lifecycle": "default",
                "Cc": [],
                "Created": "2022-03-06T04:53:38Z",
                "_hyperlinks": [
                    {
                        "_url": "http://localhost:8080/REST/2.0/queue/1",
                        "type": "queue",
                        "id": 1,
                        "ref": "self"
                    },
                    {
                        "ref": "history",
                        "_url": "http://localhost:8080/REST/2.0/queue/1/history"
                    },
                    {
                        "ref": "create",
                        "type": "ticket",
                        "_url": "http://localhost:8080/REST/2.0/ticket?Queue=1"
                    }
                ],
                "SLADisabled": "1",
                "Name": "General",
                "TicketCustomFields": [],
                "Disabled": "0",
                "TicketTransactionCustomFields": [],
                "CustomFields": [],
                "Description": "The default queue",
                "CommentAddress": "",
                "id": 1
            }

        :param queue_id: Identification of queue by name (str) or queue ID
                         (int)
        :returns: Queue details as a dictionary

        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        :raises NotFoundError: In case the queue does not exist
        """
        res = self.__request(f'queue/{queue_id}')

        if not (res is None or isinstance(res, dict)):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return res

    def get_all_queues(self, include_disabled: bool = False) -> typing.List[typing.Dict[str, typing.Any]]:
        """ Return a list of all queues.

        Example of a return result:

        .. code-block:: json

            [
                {
                    "InitialPriority": "",
                    "_url": "http://localhost:8080/REST/2.0/queue/1",
                    "type": "queue",
                    "Name": "General",
                    "DefaultDueIn": "",
                    "Description": "The default queue",
                    "CorrespondAddress": "",
                    "CommentAddress": "",
                    "id": "1",
                    "FinalPriority": ""
                }
            ]

        :param include_disabled: Set to True to also return disabled queues.

        :returns: Returns a list of dictionaries containing basic information on all queues.

        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        """
        params = {'fields': 'Name,Description,CorrespondAddress,CommentAddress,InitialPriority,FinalPriority,DefaultDueIn',
                  'find_disabled_rows': int(include_disabled)
                  }
        queues = self.__paged_request('queues/all', params=params)

        return list(queues)

    def edit_queue(self, queue_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.List[str]:
        """ Edit queue.

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
        :raises BadRequestError: When queue does not exist
        :raises InvalidUseError: When invalid fields are set
        :raises UnexpectedResponseError: If the response from RT is not as expected
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
            raise InvalidUseError(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            ret = self.__request_put(f'queue/{queue_id}', json_data=post_data)
        except UnexpectedResponseError as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            raise

        return ret

    def create_queue(self, name: str, **kwargs: typing.Any) -> int:
        """ Create queue.

        :param name: Queue name (required)
        :param kwargs: Optional fields to set (see edit_queue)
        :returns: ID of new queue or False when create fails
        :raises BadRequestError: When queue already exists
        :raises InvalidUseError: When invalid fields are set
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        valid_fields = {'Name', 'Description', 'CorrespondAddress', 'CommentAddress',
                        'Disabled', 'SLADisabled', 'Lifecycle', 'SortOrder'
                        }
        invalid_fields = []

        post_data = {'Name': name}

        for key, val in kwargs.items():
            if key not in valid_fields:
                invalid_fields.append(key)

            else:
                post_data[key] = val

        if invalid_fields:
            raise InvalidUseError(f'''Unsupported names of fields: {', '.join(invalid_fields)}.''')

        try:
            res = self.__request('queue', json_data=post_data)
        except UnexpectedResponseError as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            raise

        if not isinstance(res, dict):  # pragma: no cover
            raise UnexpectedResponseError(str(res))

        return int(res['id'])

    def delete_queue(self, queue_id: typing.Union[str, int]) -> None:
        """ Disable a queue.

        :param queue_id: Identification of queue by name (str) or ID (int)

        :returns: ID or name of edited queue or False when edit fails
        :raises BadRequestError: When queue does not exist
        :raises NotFoundError: If the queue does not exist
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        try:
            _ = self.__request_delete(f'queue/{queue_id}')
        except UnexpectedResponseError as exc:  # pragma: no cover
            if exc.status_code == 400:
                raise rt.exceptions.BadRequestError(exc.response_message) from exc

            if exc.status_code == 204:
                return

            raise  # pragma: no cover

    def get_links(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Dict[str, str]]]:
        """ Gets the ticket links for a single ticket.

        Example of a return result:

        .. code-block:: json

            [
                {
                    "id": "13",
                    "type": "ticket",
                    "_url": "http://localhost:8080/REST/2.0/ticket/13",
                    "ref": "depends-on"
                }
            ]

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
        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        """
        ticket = self.get_ticket(ticket_id)

        links = [link for link in ticket['_hyperlinks'] if link.get('type', '') == 'ticket' and link['ref'] != 'self']

        return links

    def edit_link(self, ticket_id: typing.Union[str, int], link_name: TYPE_VALID_TICKET_LINK_NAMES, link_value: typing.Union[str, int],
                  delete: bool = False) -> bool:
        """ Creates or deletes a link between the specified tickets.

        :param ticket_id: ID of ticket to edit
        :param link_name: Name of link to edit ('Parent', 'Child', 'RefersTo',
                           'ReferredToBy', 'DependsOn', 'DependedOnBy')
        :param link_value: Either ticker ID or external link.
        :param delete: if True the link is deleted instead of created
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Ticket with given ID does not exist or link to delete is
                      not found
        :raises InvalidUseError: When none or more than one link is specified. Also,
                            when a wrong link name is used or when trying to link to a deleted ticket.
        """
        if link_name not in VALID_TICKET_LINK_NAMES:
            raise InvalidUseError(f'Unsupported link name. Use one of "{", ".join(VALID_TICKET_LINK_NAMES)}".')

        if delete:
            json_data = {f'Delete{link_name}': link_value}
        else:
            json_data = {f'Add{link_name}': link_value}

        msg = self.__request_put(f'ticket/{ticket_id}', json_data=json_data)

        if msg and isinstance(msg, list):
            if msg[0].startswith('Couldn\'t resolve'):
                raise NotFoundError(msg[0])
            if 'not allowed' in msg[0]:
                raise InvalidUseError(msg[0])

        return True

    def merge_ticket(self, ticket_id: typing.Union[str, int], into_id: typing.Union[str, int]) -> bool:
        """ Merge ticket into another.

        :param ticket_id: ID of ticket to be merged
        :param into_id: ID of destination ticket
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either origin or destination ticket does not
                      exist or user does not have ModifyTicket permission.
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__request_put(f'ticket/{ticket_id}', json_data={'MergeInto': into_id})

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

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
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__request_put(f'ticket/{ticket_id}/take')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

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
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__request_put(f'ticket/{ticket_id}/untake')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

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
        :raises UnexpectedResponseError: If the response from RT is not as expected
        """
        msg = self.__request_put(f'ticket/{ticket_id}/steal')

        if not isinstance(msg, list) or len(msg) != 1:  # pragma: no cover
            raise UnexpectedResponseError(str(msg))

        self.logger.debug(str(msg))

        return msg[0].lower().startswith('owner changed')
