import pytest
from gmsa import utils

class TestUtils(object):

    def test_extract_and_format_to_header(self):
        input_str = '"Anete Gludīte" <john.doe@example.com>'
        expected_output = 'Anete Gludīte <john.doe@example.com>'
        assert utils.extract_and_format_to_header(input_str) == expected_output

    def test_extract_and_format_to_header_invalid_format(self):
        input_str = 'Anete Gludīte <john.doe@example.com>'
        with pytest.raises(ValueError):
            utils.extract_and_format_to_header(input_str)
