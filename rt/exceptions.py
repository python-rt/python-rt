"""Exceptions collection for the rt library."""


class RtError(Exception):
    """ Super class of all Rt Errors """


class AuthorizationError(RtError):
    """ Exception raised when module cannot access :term:`API` due to invalid
    or missing credentials. """


class NotAllowed(RtError):
    """ Exception raised when request cannot be finished due to
    insufficient privileges. """


class UnexpectedResponse(RtError):
    """ Exception raised when unexpected HTTP code is received. """


class UnexpectedMessageFormat(RtError):
    """ Exception raised when response has bad status code (not the HTTP code,
    but code in the first line of the body as 200 in `RT/4.0.7 200 Ok`)
    or message parsing fails because of unexpected format. """


class APISyntaxError(RtError):
    """ Exception raised when syntax error is received. """


class InvalidUse(RtError):
    """ Exception raised when API method is not used correctly. """


class BadRequest(RtError):
    """ Exception raised when HTTP code 400 (Bad Request) is received. """


class ConnectionError(RtError):
    """ Encapsulation of various exceptions indicating network problems. """

    def __init__(self, message: str, cause: Exception) -> None:
        """ Initialization of exception extented by cause parameter.

        :keyword message: Exception details
        :keyword cause: Cause exception
        """
        super().__init__(message + ' (Caused by ' + repr(cause) + ")")
        self.cause = cause


class InvalidQueryError(RtError):
    """ Exception raised when attempting to search RT with an invalid raw query. """
