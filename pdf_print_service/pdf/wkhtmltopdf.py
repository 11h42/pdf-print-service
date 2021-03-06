from __future__ import absolute_import

from copy import copy
from itertools import chain
import os
import re
import sys
import shlex

try:
    from urllib.request import pathname2url
    from urllib.parse import urljoin
except ImportError:  # Python2
    from urllib import pathname2url
    # noinspection PyUnresolvedReferences
    from urlparse import urljoin

from django.conf import settings
from django.http import HttpResponse
from django.utils import six

import logging
import subprocess


def _options_to_args(**options):
    """Converts ``options`` into a list of command-line arguments."""
    flags = []
    for name in sorted(options):
        value = options[name]
        if value is None:
            continue
        flag_name = '--' + name.replace('_', '-')
        if value is True:
            flags.append(flag_name)
        else:
            if isinstance(value, (list, tuple)):
                for v in value:
                    flags.append(flag_name)
                    if isinstance(v, (list, tuple)):
                        flags.extend(map(six.text_type, v))
                    else:
                        flags.append(six.text_type(v))
            else:
                flags.append(flag_name)
                flags.append(six.text_type(value))
    return flags


def wkhtmltopdf(pages, output=None, **kwargs):
    """
    Converts html to PDF using http://wkhtmltopdf.org/.

    pages: List of file paths or URLs of the html to be converted.
    output: Optional output file path. If None, the output is returned.
    **kwargs: Passed to wkhtmltopdf via _extra_args() (See
              https://github.com/antialize/wkhtmltopdf/blob/master/README_WKHTMLTOPDF
              for acceptable args.)
              Kwargs is passed through as arguments. e.g.:
                  {'footer_html': 'http://example.com/foot.html'}
              becomes
                  '--footer-html http://example.com/foot.html'

              Where there is no value passed, use True. e.g.:
                  {'disable_javascript': True}
              becomes:
                  '--disable-javascript'

              To disable a default option, use None. e.g:
                  {'quiet': None'}
              becomes:
                  ''

    example usage:
        wkhtmltopdf(pages=['/tmp/example.html'],
                    dpi=300,
                    orientation='Landscape',
                    disable_javascript=True)
    """
    if isinstance(pages, six.string_types):
        # Support a single page.
        pages = [pages]

    if output is None:
        # Standard output.
        output = '-'

    # Default options:
    options = getattr(settings, 'WKHTMLTOPDF_CMD_OPTIONS', None)
    if options is None:
        options = {'quiet': True}
    else:
        options = copy(options)
    options.update(kwargs)

    # Force --encoding utf8 unless the user has explicitly overridden this.
    options.setdefault('encoding', 'utf8')

    env = getattr(settings, 'WKHTMLTOPDF_ENV', None)
    if env is not None:
        env = dict(os.environ, **env)

    cmd = 'WKHTMLTOPDF_CMD'
    cmd = getattr(settings, cmd, os.environ.get(cmd, 'wkhtmltopdf'))

    ck_args = list(chain(shlex.split(cmd),
                         _options_to_args(**options),
                         list(pages),
                         [output]))
    ck_kwargs = {
        'env': env,
    }
    ck_kwargs['stdout'] = subprocess.PIPE
    ck_kwargs['stderr'] = subprocess.PIPE

    logging.debug("CMDLINE: %s %s", str(ck_args), ck_kwargs)
    timeout = None
    with subprocess.Popen(ck_args, **ck_kwargs) as process:
        try:
            stdout, stderr = process.communicate(None, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(process.args, timeout, output=stdout,
                                 stderr=stderr)
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if retcode:
            raise subprocess.CalledProcessError(retcode, process.args,
                                     output=stdout, stderr=stderr)
    return stdout


def content_disposition_filename(filename):
    """
    Sanitize a file name to be used in the Content-Disposition HTTP
    header.

    Even if the standard is quite permissive in terms of
    characters, there are a lot of edge cases that are not supported by
    different browsers.

    See http://greenbytes.de/tech/tc2231/#attmultinstances for more details.
    """
    filename = filename.replace(';', '').replace('"', '')
    return http_quote(filename)


def http_quote(string):
    """
    Given a unicode string, will do its dandiest to give you back a
    valid ascii charset string you can use in, say, http headers and the
    like.
    """
    if isinstance(string, six.text_type):
        try:
            import unidecode
            string = unidecode.unidecode(string)
        except ImportError:
            string = string.encode('ascii', 'replace')
    # Wrap in double-quotes for ; , and the like
    string = string.replace(b'\\', b'\\\\').replace(b'"', b'\\"')
    return '"{0!s}"'.format(string.decode())


def pathname2fileurl(pathname):
    """Returns a file:// URL for pathname. Handles OS-specific conversions."""
    return urljoin('file:', pathname2url(pathname))


def make_absolute_paths(content):
    """Convert all MEDIA files into a file://URL paths in order to
    correctly get it displayed in PDFs."""

    overrides = [
        {
            'root': settings.MEDIA_ROOT,
            'url': settings.MEDIA_URL,
        },
        {
            'root': settings.STATIC_ROOT,
            'url': settings.STATIC_URL,
        }
    ]
    has_scheme = re.compile(r'^[^:/]+://')

    for x in overrides:
        if not x['url'] or has_scheme.match(x['url']):
            continue

        if not x['root'].endswith('/'):
            x['root'] += '/'

        occur_pattern = '''["|']({0}.*?)["|']'''
        occurences = re.findall(occur_pattern.format(x['url']), content)
        occurences = list(set(occurences))  # Remove dups
        for occur in occurences:
            content = content.replace(occur,
                                      pathname2fileurl(x['root']) +
                                      occur[len(x['url']):])

    return content


class PDFResponse(HttpResponse):
    """HttpResponse that sets the headers for PDF output."""

    def __init__(self, content, status=200, content_type=None,
            filename=None, show_content_in_browser=None, *args, **kwargs):

        if content_type is None:
            content_type = 'application/pdf'

        super(PDFResponse, self).__init__(content=content,
                                          status=status,
                                          content_type=content_type)
        self.set_filename(filename, show_content_in_browser)

    def set_filename(self, filename, show_content_in_browser):
        self.filename = filename
        if filename:
            fileheader = 'attachment; filename={0}'
            if show_content_in_browser:
                fileheader = 'inline; filename={0}'

            filename = content_disposition_filename(filename)
            header_content = fileheader.format(filename)
            self['Content-Disposition'] = header_content
        else:
            del self['Content-Disposition']

