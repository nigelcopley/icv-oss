"""Tests for icv-core middleware."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from icv_core.middleware import CurrentUserMiddleware, _current_user, get_current_user


@pytest.fixture
def rf():
    return RequestFactory()


class TestCurrentUserMiddleware:
    """CurrentUserMiddleware stores and clears the request user."""

    def test_get_current_user_returns_none_outside_request(self):
        # Ensure clean state
        _current_user.user = None
        assert get_current_user() is None

    def test_process_request_sets_user(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        middleware.process_request(request)
        assert get_current_user() is request.user
        # Cleanup
        _current_user.user = None

    def test_process_response_clears_user(self, rf):
        from django.http import HttpResponse

        request = rf.get("/")
        request.user = AnonymousUser()
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        middleware.process_request(request)
        response = HttpResponse()
        middleware.process_response(request, response)
        assert get_current_user() is None

    def test_process_exception_clears_user(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        middleware.process_request(request)
        middleware.process_exception(request, ValueError("oops"))
        assert get_current_user() is None

    def test_get_current_user_returns_none_when_no_user_attr(self, rf):
        request = rf.get("/")
        # No user attribute on request
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        middleware.process_request(request)
        assert get_current_user() is None
        _current_user.user = None
