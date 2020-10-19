"""Test function of an actual login against a live RT instance.

 * The tests in this file all require a live RT instance that can receive
   requests.
 * The tests also require that the credential information be valid for
   permitting login to the RT instance.
 * You need to export the information about the instance as environment
   variables:
   * RT_BASE_URL: URL of your RT instance (without the "REST/2.0/" suffix)
   * RT_USER, RT_PASS: username and password that are used for normal
     authentication
   * RT_TOKEN: a valid token that will let tests contact the API.

This file aims to verify which different authentication methods work and which
don't. It will also help to track if an authentication method that's broken
will eventually be fixed in a certain RT version.
"""
import os
import unittest
import requests
from urllib.parse import urljoin, quote


class TestFunctionalRTAuthentication(unittest.TestCase):
    """Try authenticating to a live instance using different methods.

    .. seealso:: https://docs.bestpractical.com/rt/5.0.0/RT/REST2.html#Authentication-Methods
    """  # noqa: E501

    def setUp(self):
        """Grab RT credentials from the environment."""
        try:
            self.RT_BASE_URL = os.environ['RT_BASE_URL']
            self.INSTANCE_CREDENTIALS = {
                "user": os.environ['RT_USER'],
                "pass": os.environ['RT_PASS'],
            }
            self.AUTH_TOKEN = os.environ['RT_TOKEN']
        except KeyError as e:
            raise Exception(
                "Environment variable was not defined: {}".format(e))

    def test_http_basic_auth(self):
        """Use HTTP Basic Authentication to make an authenticated request.

        Contrary to what the REST2 API documents, the HTTP Basic
        Authentication does not seem to work against the REST2 API on either
        an RT 4.x or a 5.x instance.
        """
        API_URL = urljoin(self.RT_BASE_URL, "REST/2.0")
        basic_auth = (
            self.INSTANCE_CREDENTIALS["user"],
            self.INSTANCE_CREDENTIALS["pass"]
        )

        # If this test ever fails consistently, it might mean that HTTP Basic
        # Auth is suddenly working!
        with self.assertRaises(requests.exceptions.HTTPError):
            r = requests.get(API_URL, auth=basic_auth)
            r.raise_for_status()

    def test_token_auth(self):
        """Use a token to run an authenticated request to the API."""
        endpoint_url = urljoin(self.RT_BASE_URL, "REST/2.0/rt")
        prepared_token = quote(self.AUTH_TOKEN)
        headers = {
            "Authorization": "token {}".format(prepared_token),
        }

        r = requests.get(endpoint_url, headers=headers)
        r.raise_for_status()

        assert len(r.json()) == 2

    def test_http_session_cookie_auth(self):
        """Use the cookie of a session authenticated outside of the API.

        According to the API's documentation, this method is not recommended
        to be used. However, judging as to how HTTP Basic Authentication is
        currently broken, it is the only method we can use to authenticated
        without a token.
        """
        auth_url = urljoin(self.RT_BASE_URL, "NoAuth/Login.html")

        r = requests.post(auth_url, data=self.INSTANCE_CREDENTIALS)
        r.raise_for_status()

        assert len(dict(r.cookies)) == 1
