# Changelog
All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v3.0.7], 2023-07-27
### Fixes
- Fix sorting when using search() method (#90)

## [v3.0.6], 2023-06-21
### Fixes
- Fixed bug in rest1 (#86)

## [v3.0.5], 2023-02-02
### Added
- Added support for specifying custom fields on user creation/edit (#82).

## [v3.0.4], 2022-11-08
### Fixes
- Workaround for parsing issues with tickets with only 1 attachment (#80), due to probably an upstream bug.

## [v3.0.3], 2022-06-16
### Changes
- Move package metadata and configuration from setup.cfg to pyproject.toml.

## [v3.0.2], 2022-06-12
### Fixes
- Fix edit_user() response handling in case a user_id name (str) was passed instead of a number.

## [v3.0.1], 2022-05-26
### Fixes
- Make sure to include _hyperlinks in history items
- On edit ticket, raise exception if user/queue does not exist

### Added
- Add helper method for deleting tickets
- Add tests

## [v3.0.0], 2022-05-17
The following is a major release of the `rt` library.
There is support for the REST API version 1 as well as version 2.
Please note that this release contains breaking changes and requires adaptations to existing code, even if you are
sticking to version 1 of the API.
These changes were necessary in order to properly support both API versions.

### Added
- RT REST2 support was added and is mostly on par with the REST1 support (differences are a result of the REST2 API implementation differences in RT).
REST2 is a modern API based on JSON exchanges and thus the complex parsing of responses and request construction are no longer needed.

### Changes
- Existing exception classes were renamed to adhere to the naming convention (https://peps.python.org/pep-0008/#exception-names).
  - In case you do catch specific `rt` exceptions, a simple search/replace will do, see the changelog page in the documentation for details.
- Importing the `rt` class changed in order to better accommodate the new `rest2` implementation.
  - Where one use to be able to import `rt` using:
    `from rt import Rt`
  
    you now have to use the following syntax:
  
    `from rt.rest1 import Rt`
- Importing the `rt` module does no longer import all exceptions but only the core `RtError` exception.
If you require other exceptions, please import them from `rt.exceptions`.
- Use pytest instead of nose.

## [v2.2.2], 2022-04-08
- Fix bug in the get_ticket would omit certain fields in case they were empty instead of returning an empty list as was the previous behavior (#70).
- Add tests for verifying correct return result for AdminCc, Cc and Requestor fields.

## [v2.2.1], 2021-11-26
- Fix bug in get_attachment_content which was a workaround for a bug in RT <=4.2 (trailing new-lines) but which was fixed in RT >=4.2. This made tests fail and return falsely stripped attachment content.

## [v2.2.0], 2021-11-15
- Search has a parameter fields that can be used to return only particular fields for tickets. In some cases I noticed it will improve the speed of the query completion if you only need specific fields (#65 by @kimmoal).

## [v2.1.1], 2021-03-23
- Fix support for custom field values containing newlines in API responses (#10, #11)
  (the previous change in v1.0.11 fixed API requests) (#64)

## [v2.1.0], 2021-02-25
- Add the possibility to provide cookies as dict to authenticate (#60)
- Add 'Referer' header for CSRF check when cookies are used for authentication (#60)
- Add IS and IS NOT operators to search (#57)

## [v2.0.1], 2020-08-07
- Fix UnicodeDecodeError in logging code for non-text attachments (#50, #51)
- Documentation: Add a search example (#49)
- edit_ticket: Handle possible empty responses: When a ticket is not modified, at least with RT 4.x, an empty
  response could be returned. Gracefully handle that as success. (#47, #48)

## [v2.0.0], 2020-02-11
- Drop Python2 support
- Adjust Travis tests for Python3-only, and add v3.8
- Add inline typing
- Remove "debug_mode" parameter
- Add "logging" support (basically replacing "debug_mode" and the various "print"s)
- Fix "no-else-after-return" and "no-else-after-raise"
- Fix "startswitch" typos / bugs
- Removed deprecated "basic_auth" and "digest_auth" parameters. The same functionality is given by specifying the
  "http_auth" with an instance of either object. This allows for more flexibility with various other alternative
  authentication methods.

## [v1.0.13], 2020-02-06
- Add deprecation warning for in the next major release unsupported parameters (basic_auth, digest_auth).
  They are now replaced with http_auth.
- Fix problematic default method parameters ("{}" and "[]").

## [v1.0.12], 2019-10-25
- Travis CI Docker tests
- RT 4.4 fixes
- Support multiline CF values in create_ticket and edit_ticket.
- Fix support for custom field names containing colons
- In search(), replace splitlines() with lines array split on \n.
- Add debug_mode flag for response logging
- Add platform independent url joining / Allow testing on Windows
- Add numerical_id to get_ticket result

## [v1.0.11], 2018-07-16
- Added parameter to set the content type in reply() and comment() (#12).
- Added parameter Format to search() (#17).
- Tests: Update to new demo instance, fixing tests.
- Tests: Disable tests in Travis, the existing test instance closed the REST interface (#28).
- Fix support for custom field names containing colons (#37).
- Fix support for custom field values containing newlines (#11).

## [v1.0.10], 2017-02-22
- PEP8 fixes
- update .travis.yml to update python interpreter list and some other small changes
- prefer format over % (PEP 3101)
- Add patch from https://gitlab.labs.nic.cz/labs/python-rt/issues/9
  "Support CF search where special chars or spaces in CF names"
- Implement a fix for the issue suggested in
  https://gitlab.labs.nic.cz/labs/python-rt/issues/10 (can't create ticket
  with multi-line message)
- Implement fix for https://gitlab.labs.nic.cz/labs/python-rt/issues/7
  "returned types inconsistent in get_ticket"
  Add splitting for Cc and AdminCc

## [v1.0.9], 2016-06-22
- added ability to steal, untake, and explicitly take tickets
- fixed create_ticket return value when provided an invalid custom field

## [v1.0.8], 2014-05-29
- added ability to search all queues
- added RtError super class
- fixed compatibility issues with Python 2.6

## [v1.0.7], 2013-10-01
- unit tests
- own exceptions
- added create_user, create_queue, edit_user, edit_queue methods
- added edit_link (replaces buggy edit_ticket_links)
- added get_attachments, get_short_history methods
- support merge_ticket in RT4
- custom query to search method
- strict binary handling with attachments

## [v1.0.6], 2013-09-05
- added support for HTTP basic and digest authentication
- specification of errors to different exceptions

## [v1.0.5], 2013-04-26
- fixed decoding of utf-8 only when needed
- updated search function to support various
  lookup operators and sorting

## [v1.0.4], 2013-03-21
- default queue added to init parameters

## [v1.0.3], 2013-03-06
- python-requests 1.x compatible

## [v1.0.2], 2013-02-18
- HTTP proxy support
- Support for multilinks in get_links

## [v1.0.1], 2013-01-10
- Updated docstrings
- Added Sphinx documentation

## [v1.0.0], 2012-08-03
- Initial release
