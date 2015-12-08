import base64
import logging

from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.utils.six import wraps
from django.views.decorators.csrf import csrf_exempt


def basic_auth_required(view_func):
    """Decorator which ensures the credentials (user and api key) are corrects."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        username = None
        password = None

        if hasattr(request, "user") and request.user.is_authenticated():
            return view_func(request, *args, **kwargs)

        basic_auth = request.META.get('HTTP_AUTHORIZATION')
        # print(basic_auth)

        if basic_auth:
            auth_method, token = basic_auth.split(' ', 1)

            if auth_method.lower() == 'basic':
                token = base64.b64decode(token.strip()).decode()
                username, password = token.split(':', 1)

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                request.user = user
                return view_func(request, *args, **kwargs)
        logging.getLogger("auth").warning("Bad password for user '%s'", username)
        return HttpResponse(status=401)

    return _wrapped_view
