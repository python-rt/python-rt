"""
======================================================
 Rt - Python interface to Request Tracker :term:`API`
======================================================

Description of Request Tracker :term:`REST` :term:`API`:
http://requesttracker.wikia.com/wiki/REST

Provided functionality:

* login to RT
* logout
* getting, creating and editing tickets
* getting attachments
* getting history of ticket
* replying to ticket requestors
* adding comments
* getting and editing ticket links
* searching
* providing lists of last updated tickets
* providing tickets with new correspondence
* merging tickets
* take tickets
* steal tickets
* untake tickets
"""

import datetime
import logging
import re
import typing
import warnings
from urllib.parse import urljoin

import requests
import requests.auth

from .exceptions import NotAllowedError, UnexpectedResponseError, UnexpectedMessageFormatError, InvalidUseError, \
    BadRequestError, AuthorizationError, APISyntaxError, InvalidQueryError, NotFoundError

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

DEFAULT_QUEUE = 'General'
""" Default queue used. """

ALL_QUEUES = object()


class Rt:
    r""" :term:`API` for Request Tracker according to
    http://requesttracker.wikia.com/wiki/REST. Interface is based on
    :term:`REST` architecture, which is based on HTTP/1.1 protocol. This module
    is therefore mainly sending and parsing special HTTP messages.

    .. note:: Use only ASCII LF as newline (``\\n``). Time is returned in UTC.
              All strings returned are encoded in UTF-8 and the same is
              expected as input for string values.
    """

    RE_PATTERNS = {
        'not_allowed_pattern': re.compile('^# You are not allowed to'),
        'credentials_required_pattern': re.compile('.* 401 Credentials required$'),
        'syntax_error_pattern': re.compile('.* 409 Syntax Error$'),
        'requestors_pattern': re.compile('Requestors:'),
        'update_pattern': re.compile('^# Ticket [0-9]+ updated.$'),
        'content_pattern': re.compile('Content:'),
        'content_pattern_bytes': re.compile(b'Content:'),
        'attachments_pattern': re.compile('Attachments:'),
        'attachments_list_pattern': re.compile(r'[^0-9]*(\d+): (.+) \((.+) / (.+)\),?$'),
        'headers_pattern_bytes': re.compile(b'Headers:'),
        'links_updated_pattern': re.compile('^# Links for ticket [0-9]+ updated.$'),
        'created_link_pattern': re.compile('.* Created link '),
        'deleted_link_pattern': re.compile('.* Deleted link '),
        'merge_successful_pattern': re.compile('^# Merge completed.|^Merge Successful$'),
        'bad_request_pattern': re.compile('.* 400 Bad Request$'),
        'user_pattern': re.compile(r'^# User ([0-9]*) (?:updated|created)\.$'),
        'queue_pattern': re.compile(r'^# Queue (\w*) (?:updated|created)\.$'),
        'ticket_created_pattern': re.compile(r'^# Ticket ([0-9]+) created\.$'),
        'does_not_exist_pattern': re.compile(r'^# (?:Queue|User|Ticket) \w* does not exist\.$'),
        'status_pattern': re.compile(r'^\S+ (\d{3}) '),
        'does_not_exist_pattern_bytes': re.compile(br'^# (?:Queue|User|Ticket) \w* does not exist\.$'),
        'not_related_pattern': re.compile(r'^# Transaction \d+ is not related to Ticket \d+'),
        'invalid_attachment_pattern_bytes': re.compile(br'^# Invalid attachment id: \d+$'),
    }  # type: typing.Dict[str, re.Pattern]

    def __init__(self, url: str,
                 default_login: typing.Optional[str] = None,
                 default_password: typing.Optional[str] = None,
                 cookies: typing.Optional[dict] = None,
                 proxy: typing.Optional[str] = None,
                 default_queue: str = DEFAULT_QUEUE,
                 skip_login: bool = False,
                 verify_cert: typing.Optional[typing.Union[str, bool]] = True,
                 http_auth: typing.Optional[requests.auth.AuthBase] = None) -> None:
        """ API initialization.

        :keyword url: Base URL for Request Tracker API.
                      E.g.: http://tracker.example.com/REST/1.0/
        :keyword default_login: Default RT login used by self.login if no
                                other credentials are provided
        :keyword default_password: Default RT password
        :keyword proxy: Proxy server (string with http://user:password@host/ syntax)
        :keyword default_queue: Default RT queue
        :keyword skip_login: Set this option True when HTTP Basic authentication
                             credentials for RT are in .netrc file. You do not
                             need to call login, because it is managed by
                             requests library instantly.
        :keyword http_auth: Specify a http authentication instance, e.g. HTTPBasicAuth(), HTTPDigestAuth(),
                            etc. to be used for authenticating to RT
        """
        self.logger = logging.getLogger(__name__)

        # ensure trailing slash
        if not url.endswith("/"):
            url = url + "/"
        self.url = url
        self.default_login = default_login
        self.default_password = default_password
        self.default_queue = default_queue
        self.login_result = None
        self.session = requests.session()
        if cookies:
            self.session.headers.update({'referer': url})
            self.session.cookies.update(cookies)
            self.login_result = True

        self.session.verify = verify_cert
        if proxy is not None:
            if url.lower().startswith("https://"):
                self.session.proxies = {"https": proxy}
            else:
                self.session.proxies = {"http": proxy}
        if http_auth:
            self.session.auth = http_auth
        if skip_login or http_auth:
            # Assume valid credentials, because we do not need to call login()
            # explicitly with basic or digest authentication (or if this is
            # assured, that we are login in instantly)
            self.login_result = True

    def __request(self,
                  selector: str,
                  get_params: typing.Optional[typing.Dict[str, typing.Any]] = None,
                  post_data: typing.Optional[typing.Dict[str, typing.Any]] = None,
                  files: typing.Optional[typing.List[typing.Tuple[str, typing.IO, typing.Optional[str]]]] = None,
                  without_login: bool = False,
                  text_response: bool = True) -> str:
        r""" General request for :term:`API`.

        :keyword selector: End part of URL which completes self.url parameter
                           set during class initialization.
                           E.g.: ``ticket/123456/show``
        :keyword post_data: Dictionary with POST method fields
        :keyword files: List of pairs (filename, file-like object) describing
                        files to attach as multipart/form-data
                        (list is necessary to keep files ordered)
        :keyword without_login: Turns off checking last login result
                                (usually needed just for login itself)
        :keyword text_response: If set to false the received message will be
                                returned without decoding (useful for attachments)
        :returns: Requested message including state line in form
                  ``RT/3.8.7 200 Ok\\n``
        :rtype: string or bytes if text_response is False
        :raises AuthorizationError: In case that request is called without previous
                                    login or login attempt failed.
        :raises ConnectionError: In case of connection error.
        """
        try:
            if (not self.login_result) and (not without_login):
                raise AuthorizationError('First login by calling method `login`.')
            url = str(urljoin(self.url, selector))
            if not files:
                if post_data:
                    response = self.session.post(url, data=post_data)
                else:
                    response = self.session.get(url, params=get_params)
            else:
                files_data = {}
                for i, file_pair in enumerate(files):
                    files_data[f'attachment_{i + 1}'] = file_pair
                response = self.session.post(url, data=post_data, files=files_data)  # type: ignore

            method = "GET"
            if post_data or files:
                method = "POST"
            self.logger.debug("### %s", datetime.datetime.now().isoformat())
            self.logger.debug("Request URL: %s", url)
            self.logger.debug("Request method: %s", method)
            self.logger.debug("Response status code: %s", str(response.status_code))
            self.logger.debug("Response content:")
            self.logger.debug(response.content.decode(errors='ignore'))

            if response.status_code == 401:
                raise AuthorizationError('Server could not verify that you are authorized to access the requested document.')
            if response.status_code != 200:
                raise UnexpectedResponseError(f'Received status code {response.status_code} instead of 200.')
            try:
                if response.encoding:
                    result = response.content.decode(response.encoding.lower())
                else:
                    # try utf-8 if encoding is not filled
                    result = response.content.decode('utf-8')
            except LookupError as exc:
                raise UnexpectedResponseError(f'Unknown response encoding: {response.encoding}.') from exc
            except UnicodeError as exc:
                if text_response:
                    raise UnexpectedResponseError('Unknown response encoding (UTF-8 does not work).') from exc

                # replace errors - we need decoded content just to check for error codes in __check_response
                result = response.content.decode('utf-8', 'replace')
            self.__check_response(result)
            if not text_response:
                return response.content  # type: ignore
            return result
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError("Connection error", exc) from exc

    @staticmethod
    def __get_status_code(msg: str) -> typing.Optional[int]:
        """ Select status code given message.

        :keyword msg: Result message
        :returns: Status code
        :rtype: int
        """
        try:
            return int(msg.split('\n')[0].split(' ')[1])
        except (ValueError, AttributeError, LookupError):
            return None

    def __check_response(self, msg: typing.Union[str, list]) -> None:
        """ Search general errors in server response and raise exceptions when found.

        :keyword msg: Result message
        :raises NotAllowedError: Exception raised when operation was called with
                            insufficient privileges
        :raises AuthorizationError: Credentials are invalid or missing
        :raises APISyntaxError: Syntax error
        """
        if not isinstance(msg, list):
            msg = msg.split("\n")
        if (len(msg) > 2) and self.RE_PATTERNS['not_allowed_pattern'].match(msg[2]):
            raise NotAllowedError(msg[2][2:])
        if self.RE_PATTERNS['credentials_required_pattern'].match(msg[0]):
            raise AuthorizationError('Credentials required.')
        if self.RE_PATTERNS['syntax_error_pattern'].match(msg[0]):
            raise APISyntaxError(msg[2][2:] if len(msg) > 2 else 'Syntax error.')
        if self.RE_PATTERNS['bad_request_pattern'].match(msg[0]):
            raise BadRequestError(msg[3] if len(msg) > 2 else 'Bad request.')

    @staticmethod
    def __normalize_list(msg: typing.Union[str, typing.Sequence[str]]) -> typing.Sequence[str]:
        """Split message to list by commas and trim whitespace."""
        if isinstance(msg, list):
            _msg = "".join(msg)
        elif isinstance(msg, str):
            _msg = msg
        else:
            raise ValueError('Invalid parameter type.')
        if not _msg:
            return []
        return list(map(lambda x: x.strip(), _msg.split(",")))

    @classmethod
    def __parse_response_dict(cls,
                              msg: typing.Iterable[str],
                              expect_keys: typing.Iterable[str] = (),
                              ) -> typing.Dict[str, str]:
        """Parse an RT API response body into a Python dictionary

        This method knows the general format for key-value RT API responses,
        and parses them into a Python dictionary as plain string values.

        :keyword msg: A multiline string, or an iterable of string lines, with
          the RT API response body.
        :keyword expect_keys: An iterable of strings. If any of these strings
          do not appear in the response, raise an error.
        :raises UnexpectedMessageFormatError: The body did not follow the expected format,
          or an expected key was missing
        :returns: Dictionary mapping field names to value strings
        :rtype: Dictionary with string keys and string values
        """
        if isinstance(msg, str):
            msg = msg.split('\n')
        fields = {}  # type: typing.Dict[str, typing.List[str]]
        key = '<no key>'
        for line in msg:
            if (not line
                    or line.startswith('#')
                    or (not fields and cls.RE_PATTERNS['status_pattern'].match(line))
            ):
                key = '<no key>'
            elif line[0].isspace():
                try:
                    fields[key].append(line.lstrip())
                except KeyError:
                    raise UnexpectedMessageFormatError(
                            "Response has a continuation line with no field to continue",
                    ) from None
            else:
                if line.startswith('CF.{'):
                    sep = '}: '
                else:
                    sep = ': '
                key, sep, value = line.partition(sep)
                if sep:
                    key += sep[:-2]
                    fields[key] = [value]
                elif line.endswith(':'):
                    key = line[:-1]
                    fields[key] = []
                else:
                    raise UnexpectedMessageFormatError(f"Response has a line without a field name: {line}")
        for key in expect_keys:
            if key not in fields:
                raise UnexpectedMessageFormatError(f"Missing line starting with `{key}:`.")
        return {key: '\n'.join(lines) for key, lines in fields.items()}

    @classmethod
    def __parse_response_numlist(cls, msg: typing.Iterable[str],
                                 ) -> typing.List[typing.Tuple[int, str]]:
        """Parse an RT API response body into a numbered list

        The RT API for transactions and attachments returns a numbered list of
        items. This method returns 2-tuples to represent them, where the first
        item is an integer id and the second items is a string description.

        :keyword msg: A multiline string, or an iterable of string lines, with
          the RT API response body.
        :raises UnexpectedMessageFormatError: The body did not follow the expected format
        :returns: List of 2-tuples with ids and descriptions
        :rtype: List of 2-tuples (int, str)
        """
        return sorted(
                (int(key), value)
                for key, value in cls.__parse_response_dict(msg).items()
        )

    @classmethod
    def __parse_response_ticket(cls, msg: typing.Iterable[str]) -> typing.Dict[str, typing.Union[str, typing.Sequence[str]]]:
        """Parse an RT API ticket response into a Python dictionary

        :keyword msg: A multiline string, or an iterable of string lines, with
          the RT API response body.
        :raises UnexpectedMessageFormatError: The body did not follow the expected format
        :returns: Dictionary mapping field names to value strings, or lists of
          strings for the People fields Requestors, Cc, and AdminCc
        :rtype: Dictionary with string keys and values that are strings or lists
          of strings
        """
        pairs = cls.__parse_response_dict(msg, ['Requestors'])
        if not pairs.get('id', '').startswith('ticket/'):
            raise UnexpectedMessageFormatError('Response from RT didn\'t contain a valid ticket_id')
        _, _, numerical_id = pairs['id'].partition('/')
        ticket = typing.cast(typing.Dict[str, typing.Sequence[str]], pairs)
        ticket['numerical_id'] = numerical_id
        for key in ['Requestors', 'Cc', 'AdminCc']:
            try:
                ticket[key] = cls.__normalize_list(ticket[key])
            except KeyError:
                pass
        return ticket

    def login(self, login: typing.Optional[str] = None, password: typing.Optional[str] = None) -> bool:
        """ Login with default or supplied credentials.

        .. note::

            Calling this method is not necessary when HTTP basic or HTTP
            digest_auth authentication is used and RT accepts it as external
            authentication method, because the login in this case is done
            transparently by requests module. Anyway this method can be useful
            to check whether given credentials are valid or not.

        :keyword login: Username used for RT, if not supplied together with
                        *password* :py:attr:`~Rt.default_login` and
                        :py:attr:`~Rt.default_password` are used instead
        :keyword password: Similarly as *login*

        :returns: ``True``
                      Successful login
                  ``False``
                      Otherwise
        :raises AuthorizationError: In case that credentials are not supplied neither
                                    during inicialization or call of this method.
        """
        if (login is not None) and (password is not None):
            login_data = {'user': login, 'pass': password}  # type: typing.Optional[typing.Dict[str, str]]
        elif (self.default_login is not None) and (self.default_password is not None):
            login_data = {'user': self.default_login, 'pass': self.default_password}
        elif self.session.auth:
            login_data = None
        else:
            raise AuthorizationError('Credentials required, fill login and password.')
        try:
            self.login_result = self.__get_status_code(self.__request('',
                                                                      post_data=login_data,
                                                                      without_login=True)) == 200
        except AuthorizationError:
            # This happens when HTTP Basic or Digest authentication fails, but
            # we will not raise the error but just return False to indicate
            # invalid credentials
            return False
        else:
            return bool(self.login_result)

    def logout(self) -> bool:
        """ Logout of user.

        :returns: ``True``
                      Successful logout
                  ``False``
                      Logout failed (mainly because user was not login)
        """
        ret = False
        if self.login_result is True:
            ret = self.__get_status_code(self.__request('logout')) == 200
            self.login_result = None
        return ret

    def new_correspondence(self, queue: typing.Optional[typing.Union[str, object]] = None) -> typing.List[dict]:
        """ Obtains tickets changed by other users than the system one.

        :keyword queue: Queue where to search

        :returns: List of tickets which were last updated by other user than
                  the system one ordered in decreasing order by LastUpdated.
                  Each ticket is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        return self.search(Queue=queue, order='-LastUpdated', LastUpdatedBy__notexact=self.default_login)

    def last_updated(self, since: str, queue: typing.Optional[typing.Union[str, object]] = None) -> typing.List[dict]:
        """ Obtains tickets changed after given date.

        :param since: Date as string in form '2011-02-24'
        :keyword queue: Queue where to search

        :returns: List of tickets with LastUpdated parameter later than
                  *since* ordered in decreasing order by LastUpdated.
                  Each tickets is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        return self.search(Queue=queue, order='-LastUpdated', LastUpdatedBy__notexact=self.default_login, LastUpdated__gt=since)

    def search(self, Queue: typing.Optional[typing.Union[str, object]] = None, order: typing.Optional[str] = None,
               raw_query: typing.Optional[str] = None, Format: str = 'l', Fields: typing.Optional[typing.List[str]] = None,
               **kwargs: typing.Any) -> typing.List[dict]:
        r""" Search arbitrary needles in given fields and queue.

        Example::

            >>> tracker = Rt('http://tracker.example.com/REST/1.0/', 'rt-username', 'top-secret')
            >>> tracker.login()
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
                             If passing raw_query, all other \\**kwargs will be ignored.
        :keyword Format:     Format of the query:

                               - i: only `id` fields are populated
                               - s: only `id` and `subject` fields are populated
                               - l: multi-line format, all fields are populated
        :keyword kwargs:     Other arguments possible to set if not passing raw_query:

                             Requestors, Subject, Cc, AdminCc, Owner, Status,
                             Priority, InitialPriority, FinalPriority,
                             TimeEstimated, Starts, Due, Text,... (according to RT
                             fields)

                             Custom fields CF.{<CustomFieldName>} could be set
                             with keywords CF_CustomFieldName.

                             To alter lookup operators you can append one of the
                             following endings to each keyword::

                                 __exact    for operator = (default)
                                 __notexact for operator !=
                                 __gt       for operator >
                                 __lt       for operator <
                                 __like     for operator LIKE
                                 __notlike  for operator NOT LIKE
                                 __is       for operator IS
                                 __isnot    for operator IS NOT

                             Setting values to keywords constrain search
                             result to the tickets satisfying all of them.

        :returns: List of matching tickets. Each ticket is the same dictionary
                  as in :py:meth:`~Rt.get_ticket`\\.
        :raises:  UnexpectedMessageFormatError: Unexpected format of returned message.
                  InvalidQueryError: If raw query is malformed
        """
        get_params = {}
        query = []
        url = 'search/ticket'
        if Queue is not ALL_QUEUES:
            query.append(f"Queue=\'{Queue or self.default_queue}\'")
        if not raw_query:
            operators_map = {
                'gt': '>',
                'lt': '<',
                'exact': '=',
                'notexact': '!=',
                'like': ' LIKE ',
                'notlike': ' NOT LIKE ',
                'is': ' IS ',
                'isnot': ' IS NOT '
            }

            for key, value in kwargs.items():
                op = '='
                key_parts = key.split('__')
                if len(key_parts) > 1:
                    key = '__'.join(key_parts[:-1])
                    op = operators_map.get(key_parts[-1], '=')
                if key[:3] != 'CF_':
                    query.append(f"{key}{op}\'{value}\'")
                else:
                    query.append(f"'CF.{{{key[3:]}}}'{op}\'{value}\'")
        else:
            query.append(raw_query)
        get_params['query'] = ' AND '.join('(' + part + ')' for part in query)
        if order:
            get_params['orderby'] = order
        get_params['format'] = Format

        if Fields:
            get_params['fields'] = ''.join(Fields)

        msg = self.__request(url, get_params=get_params)
        lines = msg.split('\n')
        if len(lines) > 2:
            if self.__get_status_code(lines[0]) != 200 and lines[2].startswith('Invalid query: '):
                raise InvalidQueryError(lines[2])
            if lines[2].startswith('No matching results.'):
                return []

        if Format == 'l':
            return [
                self.__parse_response_ticket(ticket_msg)
                for ticket_msg in msg.split('\n--\n')
            ]
        if Format == 's':
            return [
                {'id': 'ticket/' + key, 'numerical_id': key, 'Subject': value}
                for key, value in self.__parse_response_dict(msg).items()
            ]
        if Format == 'i':
            items = []
            msgs = lines[2:]
            for msg in msgs:
                if msg == '':  # Ignore blank line at the end
                    continue
                _, ticket_id = msg.split('/', 1)
                items.append({'id': 'ticket/' + ticket_id, 'numerical_id': ticket_id})
            return items

        return []

    def get_ticket(self, ticket_id: typing.Union[str, int]) -> typing.Optional[dict]:
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
        """
        _msg = self.__request(f'ticket/{ticket_id}/show')
        status_code = self.__get_status_code(_msg)
        if status_code is not None and status_code == 200:
            msg = _msg.split('\n')
            try:
                not_found = self.RE_PATTERNS['does_not_exist_pattern'].match(msg[2])
            except IndexError:
                not_found = None

            if not_found:
                return None

            return self.__parse_response_ticket(msg)

        raise UnexpectedMessageFormatError(f'Received status code is {status_code} instead of 200.')

    @staticmethod
    def __ticket_post_data(data_source: dict) -> str:
        """Convert a dictionary of RT ticket data into a REST POST data string.

        :param data_source: Dictionary with ticket fields and values.

        :returns: Equivalent string to POST to the RT REST interface.
        """
        post_data = []
        for key in data_source:
            if key.startswith('CF_'):
                rt_key = f'CF.{{{key[3:]}}}'
            else:
                rt_key = key
            value = data_source[key]
            if isinstance(value, (list, tuple)):
                value = ', '.join(value)
            value_lines = iter(value.splitlines())
            post_data.append(f'''{rt_key}: {next(value_lines, '')}''')
            post_data.extend(' ' + line for line in value_lines)
        return '\n'.join(post_data)

    def create_ticket(self, Queue: typing.Optional[typing.Union[str, object]] = None,
                      files: typing.Optional[typing.List[typing.Tuple[str, typing.IO, typing.Optional[str]]]] = None,
                      **kwargs: typing.Any) -> int:
        """ Create new ticket and set given parameters.

        Example of message sended to ``http://tracker.example.com/REST/1.0/ticket/new``::

            content=id: ticket/new
            Queue: General
            Owner: Nobody
            Requestors: somebody@example.com
            Subject: Ticket created through REST API
            Text: Lorem Ipsum

        In case of success returned message has this form::

            RT/3.8.7 200 Ok

            # Ticket 123456 created.
            # Ticket 123456 updated.

        Otherwise::

            RT/3.8.7 200 Ok

            # Required: id, Queue

        + list of some key, value pairs, probably default values.

        :keyword Queue: Queue where to create ticket
        :keyword files: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :keyword kwargs: Other arguments possible to set:

                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Text,... (according to RT
                         fields)

                         Custom fields CF.{<CustomFieldName>} could be set
                         with keywords CF_CustomFieldName.
        :returns: ID of new ticket or ``-1``, if creating failed
        """
        kwargs['id'] = 'ticket/new'
        kwargs['Queue'] = Queue or self.default_queue
        post_data = self.__ticket_post_data(kwargs)

        if files:
            for file_info in files:
                post_data += f"\nAttachment: {file_info[0]}"

        msg = self.__request('ticket/new', post_data={'content': post_data}, files=files)
        for line in msg.split('\n')[2:-1]:
            res = self.RE_PATTERNS['ticket_created_pattern'].match(line)
            if res is not None:
                return int(res.group(1))
            warnings.warn(line[2:])
        return -1

    def edit_ticket(self, ticket_id: typing.Union[str, int], **kwargs: typing.Any) -> bool:
        """ Edit ticket values.

        :param ticket_id: ID of ticket to edit
        :keyword kwargs: Other arguments possible to set:

                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Text,... (according to RT
                         fields)

                         Custom fields CF.{<CustomFieldName>} could be set
                         with keywords CF_CustomFieldName.
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Ticket with given ID does not exist or unknown parameter
                      was set (in this case all other valid fields are changed)
        """
        post_data = self.__ticket_post_data(kwargs)
        msg = self.__request(f'ticket/{ticket_id}/edit', post_data={'content': post_data})
        if "" == msg:  # Ticket not modified
            return True
        state = msg.split('\n')[2]
        return self.RE_PATTERNS['update_pattern'].match(state) is not None

    def get_history(self, ticket_id: typing.Union[str, int],
                    transaction_id: typing.Optional[typing.Union[str, int]] = None) -> typing.Optional[typing.List[dict]]:
        """ Get set of history items.

        :param ticket_id: ID of ticket
        :keyword transaction_id: If set to None, all history items are
                                 returned, if set to ID of valid transaction
                                 just one history item is returned

        :returns: List of history items ordered increasingly by time of event.
                  Each history item is dictionary with following keys:

                  Description, Creator, Data, Created, TimeTaken, NewValue,
                  Content, Field, OldValue, Ticket, Type, id, Attachments

                  All these fields are strings, just 'Attachments' holds list
                  of pairs (attachment_id,filename_with_size).

                  Returns None if ticket or transaction does not exist.
        :raises UnexpectedMessageFormatError: Unexpected format of returned message.
        """
        if transaction_id is None:
            # We are using "long" format to get all history items at once.
            # Each history item is then separated by double dash.
            msgs = self.__request(f'ticket/{ticket_id}/history?format=l')
        else:
            msgs = self.__request(f'ticket/{ticket_id}/history/id/{transaction_id}')
        lines = msgs.split('\n')
        if (len(lines) > 2) and (
                self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]) or self.RE_PATTERNS['not_related_pattern'].match(
                lines[2])):
            return None
        items = typing.cast(
                typing.List[typing.Dict[str, typing.Union[str, typing.List[typing.Tuple[int, str]]]]],
                [self.__parse_response_dict(msg, ['Content', 'Attachments'])
                 for msg in msgs.split('\n--\n')],
        )
        for body in items:
            attachments = typing.cast(str, body.get('Attachments', ''))
            body['Attachments'] = self.__parse_response_numlist(attachments)
        return items

    def get_short_history(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Tuple[int, str]]]:
        """ Get set of short history items

        :param ticket_id: ID of ticket
        :returns: List of history items ordered increasingly by time of event.
                  Each history item is a tuple containing (id, Description).
                  Returns None if ticket does not exist.
        """
        msg = self.__request(f'ticket/{ticket_id}/history')
        lines = msg.split('\n')
        if self.__get_status_code(lines[0]) == 200:
            if (len(lines) > 2) and self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]):
                return None
            return self.__parse_response_numlist(lines)
        return []

    def __correspond(self,
                     ticket_id: typing.Union[str, int],
                     text: str = '',
                     action: str = 'correspond',
                     cc: str = '',
                     bcc: str = '',
                     content_type: str = 'text/plain',
                     files: typing.Optional[typing.List[typing.Tuple[str, typing.IO, typing.Optional[str]]]] = None) -> bool:
        """ Sends out the correspondence

        :param ticket_id: ID of ticket to which message belongs
        :keyword text: Content of email message
        :keyword action: correspond or comment
        :keyword content_type: Content type of email message, default to text/plain
        :keyword cc: Carbon copy just for this reply
        :keyword bcc: Blind carbon copy just for this reply
        :keyword files: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequestError: When ticket does not exist
        """
        post_data = {'content': """id: {}
Action: {}
Text: {}
Cc: {}
Bcc: {}
Content-Type: {}""".format(str(ticket_id), action, re.sub(r'\n', r'\n      ', text), cc, bcc, content_type)}

        if files:
            for file_info in files:
                post_data['content'] += f"\nAttachment: {file_info[0]}"
        msg = self.__request(f'ticket/{ticket_id}/comment',
                             post_data=post_data, files=files)
        return self.__get_status_code(msg) == 200

    def reply(self, ticket_id: typing.Union[str, int], text: str = '', cc: str = '', bcc: str = '',
              content_type: str = 'text/plain',
              files: typing.Optional[typing.List[typing.Tuple[str, typing.IO, typing.Optional[str]]]] = None) -> bool:
        """ Sends email message to the contacts in ``Requestors`` field of
        given ticket with subject as is set in ``Subject`` field.

        Form of message according to documentation::

            id: <ticket-id>
            Action: correspond
            Text: the text comment
                  second line starts with the same indentation as first
            Cc: <...>
            Bcc: <...>
            TimeWorked: <...>
            Attachment: an attachment filename/path

        :param ticket_id: ID of ticket to which message belongs
        :keyword text: Content of email message
        :keyword content_type: Content type of email message, default to text/plain
        :keyword cc: Carbon copy just for this reply
        :keyword bcc: Blind carbon copy just for this reply
        :keyword files: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequestError: When ticket does not exist
        """
        return self.__correspond(ticket_id, text, 'correspond', cc, bcc, content_type, files)

    def comment(self, ticket_id: typing.Union[str, int], text: str = '', cc: str = '', bcc: str = '',
                content_type: str = 'text/plain',
                files: typing.Optional[typing.List[typing.Tuple[str, typing.IO, typing.Optional[str]]]] = None) -> bool:
        """ Adds comment to the given ticket.

        Form of message according to documentation::

            id: <ticket-id>
            Action: comment
            Text: the text comment
                  second line starts with the same indentation as first
            Attachment: an attachment filename/path

        Example::

            >>> tracker = Rt('http://tracker.example.com/REST/1.0/', 'rt-username', 'top-secret')
            >>> attachment_name = sys.argv[1]
            >>> message_text = ' '.join(sys.argv[2:])
            >>> ret = tracker.comment(ticket_id, text=message_text,
            ... files=[(attachment_name, open(attachment_name, 'rb'))])
            >>> if not ret:
            ...     print('Error: could not send attachment', file=sys.stderr)
            ...     exit(1)

        :param ticket_id: ID of ticket to which comment belongs
        :keyword text: Content of comment
        :keyword content_type: Content type of comment, default to text/plain
        :keyword files: Files to attach as multipart/form-data
                        List of 2/3 tuples: (filename, file-like object, [content type])
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        :raises BadRequestError: When ticket does not exist
        """
        return self.__correspond(ticket_id, text, 'comment', cc, bcc, content_type, files)

    def get_attachments(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[typing.Tuple[str, str, str, str]]]:
        """ Get attachment list for a given ticket

        :param ticket_id: ID of ticket
        :returns: List of tuples for attachments belonging to given ticket.
                  Tuple format: (id, name, content_type, size)
                  Returns None if ticket does not exist.
        """
        msg = self.__request(f'ticket/{ticket_id}/attachments')
        lines = msg.split('\n')
        if (len(lines) > 2) and self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]):
            return None
        attachment_infos = []
        if (self.__get_status_code(lines[0]) == 200) and (len(lines) >= 4):
            # The format of tickets with 1 attachments varies from those with >=2.
            # *Attachments: ...* starts at line 3 with single attachment tickets, whereas
            # with >=2 attachment tickets, it starts at line 4. As in the latter case,
            # line 3 is just an empty line, we changed this to "3:" in order to work with
            # single attachment tickets.
            # -> Bug in RT
            for line in lines[3:]:
                info = self.RE_PATTERNS['attachments_list_pattern'].match(line)
                if info:
                    attachment_infos.append(info.groups())
        return attachment_infos  # type: ignore # type returned by the regex, if it matches, is as defined above

    def get_attachments_ids(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.List[int]]:
        """ Get IDs of attachments for given ticket.

        :param ticket_id: ID of ticket
        :returns: List of IDs (type int) of attachments belonging to given
                  ticket. Returns None if ticket does not exist.
        """
        attachments = self.get_attachments(ticket_id)
        return [int(at[0]) for at in attachments] if attachments is not None else None

    def get_attachment(self, ticket_id: typing.Union[str, int], attachment_id: typing.Union[str, int]) -> \
            typing.Optional[dict]:
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
        :raises UnexpectedMessageFormatError: Unexpected format of returned message.
        """
        _msg = self.__request(f'ticket/{ticket_id}/attachments/{attachment_id}',
                              text_response=False)
        msg = typing.cast(bytes, _msg).split(b'\n')
        if (len(msg) > 2) and (
                self.RE_PATTERNS['invalid_attachment_pattern_bytes'].match(msg[2]) or self.RE_PATTERNS['does_not_exist_pattern_bytes'].match(msg[2])):
            return None
        msg = msg[2:]
        head_matching = [i for i, m in enumerate(msg) if self.RE_PATTERNS['headers_pattern_bytes'].match(m)]
        head_id = head_matching[0] if head_matching else None
        if not head_id:
            raise UnexpectedMessageFormatError('Unexpected headers part of attachment entry. \
                                           Missing line starting with `Headers:`.')
        msg[head_id] = re.sub(b'^Headers: (.*)$', rb'\1', msg[head_id])
        cont_matching = [i for i, m in enumerate(msg) if self.RE_PATTERNS['content_pattern_bytes'].match(m)]
        if not cont_matching:
            raise UnexpectedMessageFormatError('Unexpected content part of attachment entry. \
                                           Missing line starting with `Content:`.')
        cont_id = cont_matching[0]
        pairs: typing.Dict[str, typing.Any] = {}
        for i in range(head_id):
            if b': ' in msg[i]:
                header, content = msg[i].split(b': ', 1)
                pairs[header.strip().decode('utf-8')] = content.strip().decode('utf-8')
        headers = {}
        for i in range(head_id, cont_id):
            if b': ' in msg[i]:
                header, content = msg[i].split(b': ', 1)
                headers[header.strip().decode('utf-8')] = content.strip().decode('utf-8')
        pairs['Headers'] = headers
        content = msg[cont_id][9:]
        for i in range(cont_id + 1, len(msg)):
            if msg[i][:9] == (b' ' * 9):
                content += b'\n' + msg[i][9:]
        pairs['Content'] = content
        return pairs

    def get_attachment_content(self, ticket_id: typing.Union[str, int], attachment_id: typing.Union[str, int]) -> \
            typing.Optional[bytes]:
        r""" Get content of attachment without headers.

        This function is necessary to use for binary attachment,
        as it can contain ``\\n`` chars, which would disrupt parsing
        of message if :py:meth:`~Rt.get_attachment` is used.

        Format of message::

            RT/3.8.7 200 Ok\n\nStart of the content...End of the content\n\n\n

        :param ticket_id: ID of ticket
        :param attachment_id: ID of attachment

        Returns: Bytes with content of attachment or None if ticket or
                 attachment does not exist.
        """
        msg = typing.cast(bytes, self.__request(f'ticket/{ticket_id}/attachments/{attachment_id}/content',
                                                text_response=False))
        lines = msg.split(b'\n', 3)
        if (len(lines) == 4) and (
                self.RE_PATTERNS['invalid_attachment_pattern_bytes'].match(lines[2]) or self.RE_PATTERNS['does_not_exist_pattern_bytes'].match(lines[2])):
            return None
        return msg[msg.find(b'\n') + 2:]

    def get_user(self, user_id: typing.Union[str, int]) -> typing.Optional[typing.Dict[str, str]]:
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

                  None is returned if user does not exist.
        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        """
        msg = self.__request(f'user/{user_id}')
        lines = msg.split('\n')
        status_code = self.__get_status_code(lines[0])
        if status_code is not None and status_code == 200:
            if (len(lines) > 2) and self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]):
                return None
            return self.__parse_response_dict(lines)

        raise UnexpectedMessageFormatError(f'Received status code is {status_code} instead of 200.')

    def create_user(self, Name: str, EmailAddress: str, **kwargs: typing.Any) -> typing.Union[int, bool]:
        """ Create user (undocumented API feature).

        :param Name: User name (login for privileged, required)
        :param EmailAddress: Email address (required)
        :param kwargs: Optional fields to set (see edit_user)
        :returns: ID of new user or False when create fails
        :raises BadRequestError: When user already exists
        :raises InvalidUseError: When invalid fields are set
        """
        return self.edit_user('new', Name=Name, EmailAddress=EmailAddress, **kwargs)

    def edit_user(self, user_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.Union[int, bool]:
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

        :returns: ID of edited user or False when edit fails
        :raises BadRequestError: When user does not exist
        :raises InvalidUseError: When invalid fields are set
        """
        valid_fields = {'name', 'password', 'emailaddress', 'realname',
                        'nickname', 'gecos', 'organization', 'address1', 'address2',
                        'city', 'state', 'zip', 'country', 'homephone', 'workphone',
                        'mobilephone', 'pagerphone', 'contactinfo', 'comments',
                        'signature', 'lang', 'emailencoding', 'webencoding',
                        'externalcontactinfoid', 'contactinfosystem', 'externalauthid',
                        'authsystem', 'privileged', 'disabled'}
        used_fields = set(map(lambda x: x.lower(), kwargs.keys()))

        if not used_fields <= valid_fields:
            invalid_fields = ", ".join(list(used_fields - valid_fields))
            raise InvalidUseError(f"Unsupported names of fields: {invalid_fields}.")

        if isinstance(user_id, str) and not user_id.isnumeric():
            _user = self.get_user(user_id)

            if _user is None:
                raise NotFoundError(f'User "{user_id}" does not exist.')

            user_id = _user['id'].split('/', 1)[1]

        post_data = f'id: user/{user_id}\n'
        for key, val in kwargs.items():
            post_data += f'{key}: {val}\n'
        msg = self.__request('edit', post_data={'content': post_data})
        msgs = msg.split('\n')
        if (self.__get_status_code(msg) == 200) and (len(msgs) > 2):
            match = self.RE_PATTERNS['user_pattern'].match(msgs[2])
            if match:
                return int(match.group(1))
        return False

    def get_queue(self, queue_id: typing.Union[str, int]) -> typing.Optional[typing.Dict[str, str]]:
        """ Get queue details.

        :param queue_id: Identification of queue by name (str) or queue ID
                         (int)
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

        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        """
        msg = self.__request(f'queue/{queue_id}')
        lines = msg.split('\n')
        status_code = self.__get_status_code(lines[0])
        if status_code is not None and status_code == 200:
            if (len(lines) > 2) and self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]):
                return None
            return self.__parse_response_dict(lines)

        raise UnexpectedMessageFormatError(f'Received status code is {status_code} instead of 200.')

    def edit_queue(self, queue_id: typing.Union[str, int], **kwargs: typing.Any) -> typing.Union[str, bool]:
        """ Edit queue (undocumented API feature).

        :param queue_id: Identification of queue by name (str) or ID (int)
        :param kwargs: Other fields to edit from the following list:

                          * Name
                          * Description
                          * CorrespondAddress
                          * CommentAddress
                          * InitialPriority
                          * FinalPriority
                          * DefaultDueIn

        :returns: ID or name of edited queue or False when edit fails
        :raises BadRequestError: When queue does not exist
        :raises InvalidUseError: When invalid fields are set
        """
        valid_fields = {'name', 'description', 'correspondaddress', 'commentaddress', 'initialpriority',
                        'finalpriority',
                        'defaultduein'}
        used_fields = set(map(lambda x: x.lower(), kwargs.keys()))

        if not used_fields <= valid_fields:
            invalid_fields = ", ".join(list(used_fields - valid_fields))
            raise InvalidUseError(f"Unsupported names of fields: {invalid_fields}.")
        post_data = f'id: queue/{queue_id}\n'
        for key, val in kwargs.items():
            post_data += f'{key}: {val}\n'
        msg = self.__request('edit', post_data={'content': post_data})
        msgs = msg.split('\n')
        if (self.__get_status_code(msg) == 200) and (len(msgs) > 2):
            match = self.RE_PATTERNS['queue_pattern'].match(msgs[2])
            if match:
                return match.group(1)
        return False

    def create_queue(self, Name: str, **kwargs: typing.Any) -> int:
        """ Create queue (undocumented API feature).

        :param Name: Queue name (required)
        :param kwargs: Optional fields to set (see edit_queue)
        :returns: ID of new queue or False when create fails
        :raises BadRequestError: When queue already exists
        :raises InvalidUseError: When invalid fields are set
        """
        return int(self.edit_queue('new', Name=Name, **kwargs))

    def get_links(self, ticket_id: typing.Union[str, int]) -> typing.Optional[typing.Dict[str, typing.List[str]]]:
        """ Gets the ticket links for a single ticket.

        :param ticket_id: ticket ID
        :returns: Links as lists of strings in dictionary with these keys
                  (just those which are defined):

                      * id
                      * Members
                      * MemberOf
                      * RefersTo
                      * ReferredToBy
                      * DependsOn
                      * DependedOnBy

                  None is returned if ticket does not exist.
        :raises UnexpectedMessageFormatError: In case that returned status code is not 200
        """
        msg = self.__request(f'ticket/{ticket_id}/links/show')
        lines = msg.split('\n')
        status_code = self.__get_status_code(lines[0])
        if status_code is not None and status_code == 200:
            if (len(msg) > 2) and self.RE_PATTERNS['does_not_exist_pattern'].match(lines[2]):
                return None
            pairs = self.__parse_response_dict(lines)
            return {key: [link.rstrip(',') for link in links.split()]
                    for key, links in pairs.items()}

        raise UnexpectedMessageFormatError(f'Received status code is {status_code} instead of 200.')

    def edit_ticket_links(self, ticket_id: typing.Union[str, int], **kwargs: typing.Any) -> bool:
        """ Edit ticket links.

        .. warning:: This method is deprecated in favour of edit_link method, because
           there exists bug in RT 3.8 REST API causing mapping created links to
           ticket/1. The only drawback is that edit_link cannot process multiple
           links all at once.

        :param ticket_id: ID of ticket to edit
        :keyword kwargs: Other arguments possible to set: DependsOn,
                         DependedOnBy, RefersTo, ReferredToBy, Members,
                         MemberOf. Each value should be either ticker ID or
                         external link. Int types are converted. Use empty
                         string as value to delete existing link.
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Ticket with given ID does not exist or unknown parameter
                      was set (in this case all other valid fields are changed)
        """
        post_data = ''
        for key, value in kwargs.items():
            post_data += f"{key}: {value}\n"
        msg = self.__request(f'ticket/{ticket_id}/links',
                             post_data={'content': post_data})
        state = msg.split('\n')[2]
        return self.RE_PATTERNS['links_updated_pattern'].match(state) is not None

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
        :raises InvalidUseError: When none or more then one links are specified. Also
                            when wrong link name is used.
        """
        valid_link_names = {'dependson', 'dependedonby', 'refersto',
                            'referredtoby', 'hasmember', 'memberof'}
        if not link_name.lower() in valid_link_names:
            raise InvalidUseError("Unsupported name of link.")
        post_data = {'rel': link_name.lower(),
                     'to': link_value,
                     'id': ticket_id,
                     'del': 1 if delete else 0
                     }
        msg = self.__request('ticket/link', post_data=post_data)
        state = msg.split('\n')[2]
        if delete:
            return self.RE_PATTERNS['deleted_link_pattern'].match(state) is not None

        return self.RE_PATTERNS['created_link_pattern'].match(state) is not None

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
        msg = self.__request(f'ticket/{ticket_id}/merge/{into_id}')
        state = msg.split('\n')[2]
        return self.RE_PATTERNS['merge_successful_pattern'].match(state) is not None

    def take(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Take ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      have TakeTicket permission.
        """
        post_data = {'content': f"Ticket: {ticket_id}\nAction: take"}
        msg = self.__request(f'ticket/{ticket_id}/take', post_data=post_data)
        return self.__get_status_code(msg) == 200

    def steal(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Steal ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      have StealTicket permission.
        """
        post_data = {'content': f"Ticket: {ticket_id}\nAction: steal"}
        msg = self.__request(f'ticket/{ticket_id}/take', post_data=post_data)
        return self.__get_status_code(msg) == 200

    def untake(self, ticket_id: typing.Union[str, int]) -> bool:
        """ Untake ticket

        :param ticket_id: ID of ticket to be merged
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either the ticket does not exist or user does not
                      own the ticket.
        """
        post_data = {'content': f"Ticket: {ticket_id}\nAction: untake"}
        msg = self.__request(f'ticket/{ticket_id}/take', post_data=post_data)
        return self.__get_status_code(msg) == 200

    @staticmethod
    def split_header(line: str) -> typing.Sequence[str]:
        """ Split a header line into field name and field value.

        Note that custom fields may contain colons inside the curly braces,
        so we need a special test for them.

        :param line: A message line to be split.

        :returns: (Field name, field value) tuple.
        """
        match = re.match(r'^(CF\.\{.*?}): (.*)$', line)
        if match:
            return (match.group(1), match.group(2))
        return line.split(': ', 1)
