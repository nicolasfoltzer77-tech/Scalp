class HTTPError(Exception):
    pass


def request(*args, **kwargs):
    raise NotImplementedError


def get(*args, **kwargs):
    raise NotImplementedError


def post(*args, **kwargs):
    raise NotImplementedError
