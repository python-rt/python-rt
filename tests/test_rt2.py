"""Tests for the REST2 API client."""
import unittest


from rt import rest2


REST2_URL = "http://localhost/rt/REST/2.0/"


class TestRest2(unittest.TestCase):
    """Group of test cases for the REST2 API client."""

    def test_connect_user_password(self):
        """Connection using username and password."""
        api = rest2.Rest2(REST2_URL)
        assert api._url == REST2_URL
