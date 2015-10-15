import json
import logging
import tempfile

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.utils.encoding import smart_text
from django.views.decorators.csrf import csrf_exempt

from django.views.generic import TemplateView, View
import jinja2 as jinja2
from pdf.authentication import basic_auth_required

from .wkhtmltopdf import make_absolute_paths, wkhtmltopdf
from .wkhtmltopdf import PDFResponse

log = logging.getLogger('pdf')


class MakePDFViewFromHtml(View):

    # Command-line options to pass to wkhtmltopdf
    cmd_options = {
        # 'orientation': 'portrait',
        # 'collate': True,
        # 'quiet': None,
    }

    def render_to_temporary_file(self, content, mode='w+b', bufsize=-1,
                                 suffix='.html', prefix='tmp', dir=None,
                                 delete=True):
        try:
            # Python3 has 'buffering' arg instead of 'bufsize'
            temp_file = tempfile.NamedTemporaryFile(mode=mode, buffering=bufsize,
                                          suffix=suffix, prefix=prefix,
                                          dir=dir, delete=delete)
        except TypeError:
            temp_file = tempfile.NamedTemporaryFile(mode=mode, bufsize=bufsize,
                                          suffix=suffix, prefix=prefix,
                                          dir=dir, delete=delete)

        try:
            temp_file.write(content.encode('utf-8'))
            temp_file.flush()
            return temp_file
        except:
            # Clean-up temp_file if an Exception is raised.
            temp_file.close()
            raise

    def convert_to_pdf(self, filename_or_url,
                       header_filename=None, footer_filename=None,
                       cmd_options=None):
        _cmd_options = self.cmd_options.copy()
        if cmd_options is not None:
            _cmd_options.update(cmd_options)
        # Clobber header_html and footer_html only if filenames are
        # provided. These keys may be in self.cmd_options as hardcoded
        # static files.
        if header_filename is not None:
            _cmd_options['header_html'] = header_filename
        if footer_filename is not None:
            _cmd_options['footer_html'] = footer_filename
        return wkhtmltopdf(pages=[filename_or_url], **cmd_options)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            log.warn("Unauthenticated user can't use PDF API")
            return HttpResponseForbidden()

        debug = getattr(settings, 'WKHTMLTOPDF_DEBUG', settings.DEBUG)

        params = json.loads(request.body.decode('utf-8'))
        if 'url' in params:
            # content is from remote URL
            remote_url = params['url']

            pdf_content = self.convert_to_pdf(
                filename_or_url=remote_url,
                cmd_options={
                    'print-media-type': params.get('print-media-type', True),
                    'cookie': params.get('cookies', None),#(('sessionid', request.COOKIES.get('sessionid')),)
                })
            return PDFResponse(pdf_content)

        else:
            content = self.render_jinja2(params)
            log.debug(content)

            input_file = None
            try:
                input_file = self.render_to_temporary_file(
                    content=content,
                    prefix='wkhtmltopdf-', suffix='.html',
                    delete=(not debug)
                )
                pdf_content = self.convert_to_pdf(filename_or_url=input_file.name)
                return PDFResponse(pdf_content, show_content_in_browser=False,
                                   filename='expense-claim.pdf')

            finally:
                # Clean up temporary files
                for f in filter(None, (input_file, )):
                    f.close()

    def render_jinja2(self, params):
        context_data = params['data']
        template = jinja2.Template(params['template'])
        content = smart_text(template.render(context_data))
        content = make_absolute_paths(content)
        return content


    @method_decorator(csrf_exempt)
    @method_decorator(basic_auth_required)
    def dispatch(self, request, *args, **kwargs):
        return super(MakePDFViewFromHtml, self).dispatch(request, *args, **kwargs)
