import pytest
from gmsa import utils

class TestUtils(object):

    def test_extract_and_format_to_header_with_utf8(self):
        input_str = 'Anete Gludīte <anete@example.com>'
        expected_output = '=?utf-8?q?Anete_Glud=C4=ABte?= <anete@example.com>'
        assert utils.extract_and_format_to_header(input_str) == expected_output

    def test_extract_and_format_to_header_with_quotes_and_utf8(self):
        input_str = '"Anete Gludīte" <anete@example.com>'
        expected_output = '=?utf-8?q?Anete_Glud=C4=ABte?= <anete@example.com>'
        assert utils.extract_and_format_to_header(input_str) == expected_output

    def test_extract_and_format_to_header_invalid_format(self):
        input_str = 'Anete Gludīte anete@example.com'
        with pytest.raises(ValueError, match="Input string is not in the correct format"):
            utils.extract_and_format_to_header(input_str)
