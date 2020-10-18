"""Tests for the REST2 API client."""
import unittest
from unittest.mock import patch


from rt import rest2

from requests import Session


REST2_URL = "http://localhost/rt/REST/2.0/"


class TestRest2(unittest.TestCase):
    """Group of test cases for the REST2 API client."""

    @patch('rt.rest2.requests.sessions.default_headers')
    def test_rest2_constructor(self, default_headers):
        """All instance attributes are in place in a new instance."""
        default_headers.return_value = {}
        api = rest2.Rest2(REST2_URL)
        assert api.url == REST2_URL
        assert isinstance(api.session, Session)
        assert api.session.headers == {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Charset': 'utf-8'
        }


if __name__ == '__main__':
    unittest.main()
