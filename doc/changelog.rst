Change Log
==========

Version 3.1.3 (2023-10-10)
----------------------------
Fixes
^^^^^
- Fix an issue where no e-mail was sent on ticket creation due to suggesting to use *Requestors* instead of *Requestor* (https://github.com/python-rt/python-rt/pull/92).

Version 3.1.2 (2023-09-25)
----------------------------
Fixes
^^^^^
- Revert breaking change for python3.8 (collections.abc.AsyncIterator is not subscriptable).

Version 3.1.1 (2023-09-25)
----------------------------
Fixes
^^^^^
- In AsyncRt, instead of returning sequences, return AsyncIterators.

Version 3.1.0 (2023-09-25)
----------------------------
Changes
^^^^^^^
- Replace *requests* with *httpx* for the REST2 part.

Added
^^^^^
- Add a new *AsyncRt* class which implements the RT REST2 API in asnyc.
- Adapt tests to include thew new async parts of this library.

Version 3.0.7 (2023-07-27)
----------------------------
Fixes
^^^^^
- Fix sorting when using search() method (#90)

Version 3.0.6 (2023-06-21)
----------------------------
Fixes
^^^^^
- Fixed bug in rest1 (#86)

Version 3.0.5 (2023-02-02)
----------------------------
Fixes
^^^^^
- Added support for specifying custom fields on user creation/edit (#82).

Version 3.0.4 (2022-11-08)
----------------------------
Fixes
^^^^^
- Workaround for parsing issues with tickets with only 1 attachment (#80), due to probably an upstream bug.

Version 3.0.3 (2022-06-16)
----------------------------
Changes
^^^^^^^
- Move package metadata and configuration from setup.cfg to pyproject.toml.

Version 3.0.2 (2022-06-12)
----------------------------
Fixes
^^^^^
- Fix edit_user() response handling in case a user_id name (str) was passed instead of a number.

Version 3.0.1 (2022-05-26)
----------------------------
Fixes
^^^^^
- Make sure to include _hyperlinks in history items
- On edit ticket, raise exception if user/queue does not exist

Added
^^^^^
- Add helper method for deleting tickets
- Add tests

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
