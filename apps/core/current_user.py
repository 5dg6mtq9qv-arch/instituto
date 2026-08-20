import threading


_local = threading.local()


def set_current_request(request):
    _local.request = request


def get_current_request():
    return getattr(_local, "request", None)
