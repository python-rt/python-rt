Change Log
==========

Version 3.0.0 (2022-05-17)
----------------------------
The following is a major release of the `rt` library.
There is support for the REST API version 1 as well as version 2.
Please note that this release contains breaking changes and requires adaptations to existing code, even if you are
sticking to version 1 of the API.
These changes were necessary in order to properly support both API versions.

Importing
^^^^^^^^^
Previously doing:

    .. code-block:: python

        import rt
        c = rt.Rt(...)

was enough to import the main class `Rt` as well as all exception classes.
Starting with version 3, only the main exception class `RtError` is imported when importing the `rt` module.

In order to continue using the API version 1 you need to explicitly import it from the `rest1` submodule:

    .. code-block:: python

        import rt.rest1
        c = rt.rest1.Rt(...)

If you need access to specific exception class, make sure to import the exceptions module:

    .. code-block:: python

        import rt.exceptions

Everything else is the same as with version 2 of the library.

.. WARNING::
    The minimum supported version of python has been raised to 3.7.

Exception classes
^^^^^^^^^^^^^^^^^^
Some exception classes were renamed to follow proper naming scheme (https://peps.python.org/pep-0008/#exception-names):

.. csv-table::
   :header: "<3.0.0", ">=3.0.0"
   :widths: 15, 15

    "NotAllowed", "NotAllowedError"
    "UnexpectedResponse", "UnexpectedResponseError"
    "UnexpectedMessageFormat", "UnexpectedMessageFormatError"
    "InvalidUseError", "InvalidUseError"
    "BadRequestError", "BadRequestError"
