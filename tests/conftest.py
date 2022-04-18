import pytest
import requests.auth
import typing

if typing.TYPE_CHECKING:
    import rt.rest2

# blank setup defaults
RT_URL = 'http://localhost:8080/REST/2.0/'
RT_USER = 'root'
RT_PASSWORD = 'password'
RT_QUEUE = 'General'


@pytest.fixture(scope='session')
def rt_connection() -> 'rt.rest2.Rt':
    """Setup a generic connection."""
    import rt.rest2
    return rt.rest2.Rt(url=RT_URL, http_auth=requests.auth.HTTPBasicAuth(RT_USER, RT_PASSWORD), http_timeout=None)
