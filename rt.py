import re
import os
import urllib
import pycurl
import StringIO

""" Python library :term:`API` to Request Tracker's :term:`REST` interface.

Implements functions needed by Malicious Domain Manager (https://git.nic.cz/redmine/projects/mdm), but is not directly connected with it, so this library can also be use separatly.

Description of Request Tracker REST API: http://requesttracker.wikia.com/wiki/REST

Provided functionality: login to RT, logout, getting, creating and editing
tickets, getting attachments, getting history of ticket, replying to ticket
requestors, adding comments, getting and editing ticket links, searching,
providing lists of last updated tickets and tickets with new correspondence
and merging tickets.
"""

__license__ = """ Copyright (C) 2012 CZ.NIC, z.s.p.o.

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
  '"Jiri Machalek" <jiri.machalek@nic.cz>'
]


class Rt:
    """ :term:`API` for Request Tracker according to
    http://requesttracker.wikia.com/wiki/REST. Interface is based on REST
    architecture, which is based on HTTP/1.1 protocol. This library is
    therefore mainly sending and parsing special HTTP messages.
    
    .. note:: Use only ASCII LF as newline (``\\n``). Time is returned in UTC.
              All strings returned are encoded in UTF-8 and the same is
              expected as input for string values.
    """

    def __init__(self, url, default_login=None, default_password=None):
        """ API initialization.
        
        :keyword url: Base URL for Request Tracker API.
                      E.g.: http://tracker.example.com/REST/1.0/
        :keyword default_login: Default RT login used by self.login if no
                                other credentials are provided
        :keyword default_password: Default RT password
        """
        self.url = url
        self.default_login = default_login
        self.default_password = default_password

    def __request(self, url, post_data=''):
        """ General request for :term:`API`.
 
        :keyword url: End part of URL compliting self.url parameter set during
                      class inicialization. E.g.: ``ticket/123456/show``
        :keywork post_data: Content of HTTP message, should be in the standard
                            application/x-www-form-urlencoded format
        :returns: Requested messsage including state line in form
                  ``RT/3.8.7 200 Ok\\n``
        :rtype: string
        :raises Exception: In case that request is called without previous
                           login or any other connection error.
        """
        try:
            if hasattr(self, 'curl_connect'):
                if post_data:
                    self.curl_connect.setopt(pycurl.POSTFIELDS, post_data)
                    self.curl_connect.setopt(pycurl.POST, 1)
                else:
                    self.curl_connect.setopt(pycurl.POSTFIELDS, '')
                    self.curl_connect.setopt(pycurl.POST, 0)
                self.curl_connect.setopt(pycurl.URL, str(os.path.join(self.url, url)))
                response = StringIO.StringIO()
                self.curl_connect.setopt(pycurl.WRITEFUNCTION, response.write)
                self.curl_connect.perform()
                return response.getvalue()
            else:
                raise Exception('Log in required')
        except pycurl.error as e:
            raise Exception('Request error: %r' % (e,))
    
    def __get_status_code(self, msg):
        """ Select status code given message.

        :returns: Status code
        :rtype: int
        """
        return int(msg.split('\n')[0].split(' ')[1])

    def login(self, login=None, password=None):
        """ Login with default or supplied credetials.
        
        :keyword login: Username used for RT, if not supplied together with
                        *password* :py:attr:`~Rt.default_login` and
                        :py:attr:`~Rt.default_password` are used instead
        :keyword password: Similarly as *login*
        
        :returns: ``True``
                      Successful login
                  ``False``
                      Otherwise
        :raises Exception: In case that credentials are not supplied neither
                           during inicialization or call of this method.
        """
        HEADERS = ['Accept-Language: en-us;q=0.7,en;q=0.3',
                   'Accept-Charset: utf-8',
                   'Keep-Alive: 300',
                   'Connection: Keep-Alive']
        self.curl_connect = pycurl.Curl()
        self.curl_connect.setopt(pycurl.ENCODING, '')
        self.curl_connect.setopt(pycurl.HTTPHEADER, HEADERS)
        self.curl_connect.setopt(pycurl.COOKIEFILE, '')
        self.curl_connect.setopt(pycurl.FOLLOWLOCATION, 1)

        if (login != None) and (password != None):
            login_data = {'user':login, 'pass':password}
        elif (self.default_login != None) and (self.default_password != None):
            login_data = {'user':self.default_login, 'pass':self.default_password}
        else:
            raise Exception('Credentials required')

        login_data_encoded = urllib.urlencode(login_data)
        return self.__get_status_code(self.__request('', login_data_encoded)) == 200

    def logout(self):
        """ Logout of user.
        
        :returns: ``True``
                      Successful logout
                  ``False``
                      Logout failed (mainly because user was not login)
        """
        ret = False
        if hasattr(self, 'curl_connect'):
            ret = self.__get_status_code(self.__request('logout')) == 200
            self.curl_connect.close()
            del self.curl_connect
        return ret
        
    def new_correspondence(self, queue='General'):
        """ Obtains tickets changed by other users than the system one.
        
        :keyword queue: Queue where to search
        
        :returns: List of tickets which were last updated by other user than
                  the system one ordered in decreasing order by LastUpdated.
                  Each ticket is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        msgs = self.__request('search/ticket?query=Queue=\'%s\'+AND+(LastUpdatedBy!=\'%s\')&orderby=-LastUpdated&format=l' % (queue, self.default_login))
        msgs = msgs.split('\n--\n')
        items = []
        try:
            for i in range(len(msgs)):
                pairs = {}
                msg = msgs[i].split('\n')
                for i in range(len(msg)):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
                if len(pairs) > 0:
                    items.append(pairs)    
            return items
        except:
            return []
        
    def last_updated(self, since, queue='General'):
        """ Obtains tickets changed after given date.
        
        :param since: Date as string in form '2011-02-24'
        :keyword queue: Queue where to search
        
        :returns: List of tickets with LastUpdated parameter later than
                  *since* ordered in decreasing order by LastUpdated.
                  Each tickets is dictionary, the same as in
                  :py:meth:`~Rt.get_ticket`.
        """
        msgs = self.__request('search/ticket?query=(Queue=\'%s\')+AND+(LastUpdatedBy!=\'%s\')+AND+(LastUpdated>\'%s\')&orderby=-LastUpdated&format=l' % (queue, self.default_login, since))
        msgs = msgs.split('\n--\n')
        items = []
        try:
            for i in range(len(msgs)):
                pairs = {}
                msg = msgs[i].split('\n')
                for i in range(len(msg)):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
                if len(pairs)>0:
                    items.append(pairs)    
            return items
        except:
            return []

    def search(self, Queue='General', **kwargs):
        """ Search arbitrary needles in given fields and queue.
        
        Example::
            
            >>> tracker = Rt('http://tracker.example.com/REST/1.0/', 'rt-username', 'top-secret')
            >>> tracker.login()
            >>> tickets = tracker.search(CF_Domain='example.com')

        :keyword Queue: Queue where to search
        :keyword kwargs: Other arguments possible to set:
                         
                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Text,... (according to RT
                         fields)

                         Setting value for this arguments constrain search
                         results for only tickets exactly matching all
                         arguments.

                         Custom fields CF.{<CustomFieldName>} could be set
                         with keywords CF_CustomFieldName.
        
        :returns: List of matching tickets. Each ticket is the same dictionary
                  as in :py:meth:`~Rt.get_ticket`.
        :raises Exception: Unexpected format of returned message.
        """
        query = 'search/ticket?query=(Queue=\'%s\')' % (Queue,)
        for key in kwargs:
            if key[:3] != 'CF_':
                query += "+AND+(%s=\'%s\')" % (key, kwargs[key])
            else:
                query += "+AND+(CF.{%s}=\'%s\')" % (key[3:], kwargs[key])
        query += "&format=l"

        msgs = self.__request(query)
        msgs = msgs.split('\n--\n')
        items = []
        try:
            if not hasattr(self, 'requestors_pattern'):
                self.requestors_pattern = re.compile('Requestors:')
            for i in range(len(msgs)):
                pairs = {}
                msg = msgs[i].split('\n')

                req_id = [id for id in range(len(msg)) if self.requestors_pattern.match(msg[id]) != None]
                if len(req_id)==0:
                    raise Exception('Non standard ticket.')
                else:
                    req_id = req_id[0]
                for i in range(req_id):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
                requestors = [msg[req_id][12:]]
                req_id += 1
                while (req_id < len(msg)) and (msg[req_id][:12] == ' '*12):
                    requestors.append(msg[req_id][12:])
                    req_id += 1
                pairs['Requestors'] = requestors
                for i in range(req_id,len(msg)):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
                if len(pairs) > 0:
                    items.append(pairs)    
            return items
        except:
            return []

    def get_ticket(self, ticket_id):
        """ Fetch ticket by its ID.
        
        :param ticket_id: ID of demanded ticket
        
        :returns: Dictionary with key, value pairs for ticket with
                  *ticket_id*. List of keys:
                  
                      * id
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
        :raises Exception: Unexpected format of returned message.
        """
        msg = self.__request('ticket/%s/show' % (str(ticket_id),))
        if(self.__get_status_code(msg) == 200):
            pairs = {}
            msg = msg.split('\n')

            if not hasattr(self, 'requestors_pattern'):
                self.requestors_pattern = re.compile('Requestors:')
            req_id = [id for id in range(len(msg)) if self.requestors_pattern.match(msg[id]) != None]
            if len(req_id)==0:
                raise Exception('Non standard ticket.')
            else:
                req_id = req_id[0]
            for i in range(req_id):
                colon = msg[i].find(': ')
                if colon > 0:
                    pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
            requestors = [msg[req_id][12:]]
            req_id += 1
            while (req_id < len(msg)) and (msg[req_id][:12] == ' '*12):
                requestors.append(msg[req_id][12:])
                req_id += 1
            pairs['Requestors'] = requestors
            for i in range(req_id,len(msg)):
                colon = msg[i].find(': ')
                if colon > 0:
                    pairs[msg[i][:colon].strip()] = msg[i][colon+1:].strip()
            return pairs
        else:
            raise Exception('Connection error')

    def create_ticket(self, Queue='General', **kwargs):
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
        :keyword kwargs: Other arguments possible to set:
                         
                         Requestors, Subject, Cc, AdminCc, Owner, Status,
                         Priority, InitialPriority, FinalPriority,
                         TimeEstimated, Starts, Due, Text,... (according to RT
                         fields)

                         Custom fields CF.{<CustomFieldName>} could be set
                         with keywords CF_CustomFieldName.
        :returns: ID of new ticket or ``-1``, if creating failed
        """

        post_data = 'id: ticket/new\nQueue: %s\n'%(Queue)
        for key in kwargs:
            if key[:3] != 'CF_':
                post_data += "%s: %s\n"%(key, kwargs[key])
            else:
                post_data += "CF.{%s}: %s\n"%(key[3:], kwargs[key])
        msg = self.__request('ticket/new', urllib.urlencode({'content':post_data}))
        state = msg.split('\n')[2]
        res = re.search(' [0-9]+ ',state)
        if res != None:
            return int(state[res.start():res.end()])
        else:
            return -1

    def edit_ticket(self, ticket_id, **kwargs):
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
        post_data = ''
        for key in kwargs:
            if key[:3] != 'CF_':
                post_data += "%s: %s\n"%(key, kwargs[key])
            else:
                post_data += "CF.{%s}: %s\n" % (key[3:], kwargs[key])
        msg = self.__request('ticket/%s/edit' % (str(ticket_id)), urllib.urlencode({'content':post_data}))
        state = msg.split('\n')[2]
        if not hasattr(self, 'update_pattern'):
            self.update_pattern = re.compile('^# Ticket [0-9]+ updated.$')
        return self.update_pattern.match(state) != None

    def get_history(self, ticket_id, transaction_id=None):
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
        :raises Exception: Unexpected format of returned message.
        """
        if transaction_id == None:
            # We are using "long" format to get all history items at once.
            # Each history item is then separated by double dash.
            msgs = self.__request('ticket/%s/history?format=l' % (str(ticket_id),))
        else:
            msgs = self.__request('ticket/%s/history/id/%s' % (str(ticket_id), str(transaction_id)))
        msgs = msgs.split('\n--\n')
        items = []
        try:
            if not hasattr(self, 'content_pattern'):
                self.content_pattern = re.compile('Content:')
            if not hasattr(self, 'attachments_pattern'):
                self.attachments_pattern = re.compile('Attachments:')
            for i in range(len(msgs)):
                pairs = {}
                msg = msgs[i].split('\n')
                cont_id = [id for id in range(len(msg)) if self.content_pattern.match(msg[id]) != None]
                if len(cont_id) == 0:
                    raise Exception('Unexpected history entry. \
                                     Missing line starting with `Content:`.')
                else:
                    cont_id = cont_id[0]
                atta_id = [id for id in range(len(msg)) if self.attachments_pattern.match(msg[id]) != None]
                if len(atta_id) == 0:
                    raise Exception('Unexpected attachment part of history entry. \
                                     Missing line starting with `Attachements:`.')
                else:
                    atta_id = atta_id[0]
                for i in range(cont_id):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
                content = msg[cont_id][9:]
                cont_id += 1
                while (cont_id < len(msg)) and (msg[cont_id][:9] == ' ' * 9):
                    content += '\n'+msg[cont_id][9:]
                    cont_id += 1
                pairs['Content'] = content
                for i in range(cont_id, atta_id):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
                attachments = []
                for i in range(atta_id + 1, len(msg)):
                    colon = msg[i].find(': ')
                    if colon > 0:
                        attachments.append((int(msg[i][:colon].strip()),
                                            msg[i][colon + 1:].strip()))
                pairs['Attachments'] = attachments
                items.append(pairs)    
            return items
        except:
            return []
    
    def reply(self, ticket_id, text='', cc='', bcc=''):
        """ Sends email message to the contacts in ``Requestors`` field of
        given ticket with subject as is set in ``Subject`` field. Without
        attachments now.
        
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
        :keyword cc: Carbon copy just for this reply
        :keyword bcc: Blind carbon copy just for this reply
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        """
        post_data = {'content':"""id: %s
Action: correspond
Text: %s
Cc: %s
Bcc: %s"""%(str(ticket_id), re.sub(r'\n', r'\n      ', text), cc, bcc)}
        msg = self.__request('ticket/%s/comment' % (str(ticket_id),),
                             urllib.urlencode(post_data))
        return self.__get_status_code(msg) == 200

    def comment(self, ticket_id, text='', cc='', bcc=''):
        """ Adds comment to the given ticket Without attachments now.
        
        Form of message according to documentation::

            id: <ticket-id>
            Action: comment
            Text: the text comment
                  second line starts with the same indentation as first
            Attachment: an attachment filename/path

        :param ticket_id: ID of ticket to which comment belongs
        :keyword text: Content of comment
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Sending failed (status code != 200)
        """
        post_data = {'content':"""id: %s
Action: comment
Text: %s""" % (str(ticket_id), re.sub(r'\n', r'\n      ', text))}
        msg = self.__request('ticket/%s/comment' % (str(ticket_id),),
                             urllib.urlencode(post_data))
        return self.__get_status_code(msg) == 200
        
        
    def get_attachments_ids(self, ticket_id):
        """ Get IDs of attachments for given ticket.
        
        :param ticket_id: ID of ticket
        :returns: List of IDs (type int) of attachments belonging to given
                  ticket
        """
        at = self.__request('ticket/%s/attachments' % (str(ticket_id),))
        if (len(at) != 0) and (self.__get_status_code(at) == 200):
            atlines = at.split('\n')
            if len(atlines) >= 4:
                return [int(re.sub(r'[^0-9]*([0-9]+):.*', r'\1', line)) for line in atlines[4:] if len(line) > 0]
            else:
                return []
        else:
            return []
        
    def get_attachment(self, ticket_id, attachment_id):
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
                      * Content
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
        :raises Exception: Unexpected format of returned message.
        """
        msg = self.__request('ticket/%s/attachments/%s' % (str(ticket_id), str(attachment_id)))
        msg = msg.split('\n')[2:]
        if not hasattr(self, 'headers_pattern'):
            self.headers_pattern = re.compile('Headers:')
        head_id = [id for id in range(len(msg)) if self.headers_pattern.match(msg[id]) != None]
        if len(head_id) == 0:
            raise Exception('Unexpected headers part of attachment entry. \
                             Missing line starting with `Headers:`.')
        else:
            head_id = head_id[0]
        msg[head_id] = re.sub(r'^Headers: (.*)$', r'\1', msg[head_id])
        if not hasattr(self, 'content_pattern'):
            self.content_pattern = re.compile('Content:')
        cont_id = [id for id in range(len(msg)) if self.content_pattern.match(msg[id]) != None]
        
        if len(cont_id) == 0:
            raise Exception('Unexpected content part of attachment entry. \
                             Missing line starting with `Content:`.')
        else:
            cont_id = cont_id[0]
        pairs = {}
        for i in range(head_id):
            colon = msg[i].find(': ')
            if colon > 0:
                pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
        headers = {}
        for i in range(head_id, cont_id):
            colon = msg[i].find(': ')
            if colon > 0:
                headers[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
        pairs['Headers'] = headers
        content = msg[cont_id][9:]
        for i in range(cont_id+1, len(msg)):
            if msg[i][:9] == (' ' * 9):
                content += '\n' + msg[i][9:]
        pairs['Content'] = content
        return pairs

    def get_attachment_content(self, ticket_id, attachment_id):
        """ Get content of attachment without headers.

        This function is necessary to use for binary attachment,
        as it can contain ``\\n`` chars, which would disrupt parsing
        of message if :py:meth:`~Rt.get_attachment` is used.
        
        Format of message::

            RT/3.8.7 200 Ok\n\nStart of the content...End of the content\n\n\n
        
        :param ticket_id: ID of ticket
        :param attachment_id: ID of attachment
        
        Returns: string with content of attachment
        """
    
        msg = self.__request('ticket/%s/attachments/%s/content' % (str(ticket_id), str(attachment_id)))
        return msg[re.search('\n', msg).start() + 2:-3]

    def get_user(self, user_id):
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
        :raises Exception: In case that returned status code is not 200
        """
        msg = self.__request('user/%s' % (str(user_id),))

        if(self.__get_status_code(msg) == 200):
            pairs = {}
            msg = msg.split('\n')[2:]
            for i in range(len(msg)):
                colon = msg[i].find(': ')
                if colon > 0:
                    pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
            return pairs
        else:
            raise Exception('Connection error')

    def get_queue(self, queue_id):
        """ Get queue details.
        
        :param queue_id: Identification of queue by name (str) or queue ID
                        (int)
        :returns: Queue details as strings in dictionary with these keys
                  (if queue exists):

                      * id
                      * Name
                      * Description
                      * CorrespondAddress
                      * CommentAddress
                      * InitialPriority
                      * FinalPriority
                      * DefaultDueIn

        :raises Exception: In case that returned status code is not 200
        """
        msg = self.__request('queue/%s' % str(queue_id))

        if(self.__get_status_code(msg) == 200):
            pairs = {}
            msg = msg.split('\n')[2:]
            for i in range(len(msg)):
                colon = msg[i].find(': ')
                if colon > 0:
                    pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
            return pairs
        else:
            raise Exception('Connection error')

    def get_links(self, ticket_id):
        """ Gets the ticket links for a single ticket.
        
        :param ticket_id: ticket ID
        :returns: Links as strings in dictionary with these keys
                  (just those which are defined):

                      * id
                      * Members
                      * MemberOf
                      * RefersTo
                      * ReferredToBy
                      * DependsOn
                      * DependedOnBy

        :raises Exception: In case that returned status code is not 200
        """
        msg = self.__request('ticket/%s/links/show' % (str(ticket_id),))

        if(self.__get_status_code(msg) == 200):
            pairs = {}
            msg = msg.split('\n')[2:]
            for i in range(len(msg)):
                colon = msg[i].find(': ')
                if colon > 0:
                    pairs[msg[i][:colon].strip()] = msg[i][colon + 1:].strip()
            return pairs
        else:
            raise Exception('Connection error')

    def edit_ticket_links(self, ticket_id, **kwargs):
        """ Edit ticket links.
    
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
        for key in kwargs:
            post_data += "%s: %s\n"%(key, str(kwargs[key]))
        msg = self.__request('ticket/%s/links' % (str(ticket_id),),
                             urllib.urlencode({'content':post_data}))
        state = msg.split('\n')[2]
        if not hasattr(self, 'links_updated_pattern'):
            self.links_updated_pattern = re.compile('^# Links for ticket [0-9]+ updated.$')
        return self.links_updated_pattern.match(state) != None

    def merge_ticket(self, ticket_id, into_id, **kwargs):
        """ Merge ticket into another (undocumented API feature)
    
        :param ticket_id: ID of ticket to be merged
        :param into: ID of destination ticket
        :returns: ``True``
                      Operation was successful
                  ``False``
                      Either origin or destination ticket does not
                      exist or user does not have ModifyTicket permission.
        """
        msg = self.__request('ticket/merge/%s' % (str(ticket_id),),
                             urllib.urlencode({'into':into_id}))
        state = msg.split('\n')[2]
        if not hasattr(self, 'merge_successful_pattern'):
            self.merge_successful_pattern = re.compile('^Merge Successful$')
        return self.merge_successful_pattern.match(state) != None

