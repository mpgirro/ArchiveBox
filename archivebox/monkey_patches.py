__package__ = 'archivebox'

import django
import pydantic
import shutil

import django_stubs_ext

django_stubs_ext.monkeypatch()


# monkey patch django timezone to add back utc (it was removed in Django 5.0)
import datetime
from django.utils import timezone
timezone.utc = datetime.timezone.utc

# monkey patch django-signals-webhooks to change how it shows up in Admin UI
# from signal_webhooks.apps import DjangoSignalWebhooksConfig
# DjangoSignalWebhooksConfig.verbose_name = 'API'


# Install rich for pretty tracebacks in console logs
# https://rich.readthedocs.io/en/stable/traceback.html#traceback-handler
from rich.traceback import install

install(show_locals=True, word_wrap=False, locals_max_length=10, locals_hide_dunder=True, suppress=[django, pydantic], extra_lines=2, width=shutil.get_terminal_size((100, 10)).columns - 1)


from daphne import access

class ModifiedAccessLogGenerator(access.AccessLogGenerator):
    """Clutge workaround until daphne uses the Python logging framework. https://github.com/django/daphne/pull/473/files"""
    
    def write_entry(self, host, date, request, status=None, length=None, ident=None, user=None):
        
        # Ignore noisy requests to staticfiles / favicons / etc.
        if 'GET /static/' in request:
            return
        if "GET /health/" in request:
            return
        if 'GET /admin/jsi18n/' in request:
            return
        if request.endswith("/favicon.ico") or request.endswith("/robots.txt") or request.endswith("/screenshot.png"):
            return
        if request.endswith('.css') or request.endswith('.js') or request.endswith('.woff') or request.endswith('.ttf'):
            return
        if str(status) in ('404', '304'):
            return
        
        # clean up the log format to mostly match the same format as django.conf.settings.LOGGING rich formats
        self.stream.write(
            "[%s] HTTP     %s (%s) %s\n"
            % (
                date.strftime("%Y-%m-%d %H:%M:%S"),
                request,
                status or "-",
                "localhost" if host.startswith("127.") else host.split(":")[0],
            )
        )
        
access.AccessLogGenerator.write_entry = ModifiedAccessLogGenerator.write_entry
