"""Middleware for icv-core."""

import threading

from django.utils.deprecation import MiddlewareMixin

_current_user = threading.local()


def get_current_user():
    """
    Return the current request user set by CurrentUserMiddleware.

    Returns None outside of a request context (e.g., management commands,
    Celery tasks). Always returns None if CurrentUserMiddleware is not active.
    """
    return getattr(_current_user, "user", None)


class CurrentUserMiddleware(MiddlewareMixin):
    """
    Makes the current request user available to models for
    created_by/updated_by population.

    Required when ICV_CORE_TRACK_CREATED_BY=True. Must be placed after
    Django's AuthenticationMiddleware in the MIDDLEWARE setting.

    Example::

        MIDDLEWARE = [
            ...
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "icv_core.middleware.CurrentUserMiddleware",
            ...
        ]
    """

    def process_request(self, request) -> None:
        _current_user.user = getattr(request, "user", None)

    def process_response(self, request, response):
        _current_user.user = None
        return response

    def process_exception(self, request, exception) -> None:
        _current_user.user = None
