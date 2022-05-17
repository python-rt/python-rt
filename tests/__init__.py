import random
import string


def random_string(length: int = 15) -> str:
    """Return a random string."""
    return ''.join([random.choice(string.ascii_letters) for i in range(length)])
