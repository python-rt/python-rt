"""Exceptions collection for the rt library."""

import typing


class RtError(Exception):
    """ Super class of all Rt Errors """


class AuthorizationError(RtError):
    """ Exception raised when module cannot access :term:`API` due to invalid
    or missing credentials. """


class NotAllowedError(RtError):
    """ Exception raised when request cannot be finished due to
    insufficient privileges. """


class UnexpectedResponseError(RtError):
    """ Exception raised when unexpected HTTP code is received. """

    def __init__(self, message: str, status_code: typing.Optional[int] = None, response_message: typing.Optional[str] = None) -> None:
        """ Initialization."""
        super().__init__(message)
        self.status_code = status_code
        self.response_message = response_message


class UnexpectedMessageFormatError(RtError):
    """ Exception raised when response has bad status code (not the HTTP code,
    but code in the first line of the body as 200 in `RT/4.0.7 200 Ok`)
    or message parsing fails because of unexpected format. """


class NotFoundError(RtError):
    """Exception raised if requested resource is not found."""


class APISyntaxError(RtError):
    """ Exception raised when syntax error is received. """


class InvalidUseError(RtError):
    """ Exception raised when API method is not used correctly. """


class BadRequestError(RtError):
    """ Exception raised when HTTP code 400 (Bad Request) is received. """


class ConnectionError(RtError):
    """ Encapsulation of various exceptions indicating network problems. """

    def __init__(self, message: str, cause: Exception) -> None:
        """ Initialization of exception extended by cause parameter.

        :keyword message: Exception details
        :keyword cause: Cause exception
        """
        super().__init__(f'{message} (Caused by {repr(cause)})')
        self.cause = cause


class InvalidQueryError(RtError):
    """ Exception raised when attempting to search RT with an invalid raw query. """
