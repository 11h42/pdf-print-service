from django.test import TestCase


# Create your tests here.
from pdf.wkhtmltopdf import _options_to_args


class WkHtmlToPdfTestCase(TestCase):
    def test_options_to_args(self):
        self.assertListEqual(['--boolean-param',
                              '--param1', 'value1',
                              '--param2', 'value2a', '--param2', 'value2b',
                              '--param3', 'value3a1', 'value3a2', '--param3', 'value3b1', 'value3b2',
                              ],
                             _options_to_args(
                                 param1='value1',
                                 param2=('value2a', 'value2b'),
                                 param3=(('value3a1', 'value3a2'), ('value3b1', 'value3b2')),
                                 boolean_param=True,
                                 removed_param=None
                             ))
