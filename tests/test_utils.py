from gmsa import utils
# from gmsa import extract_and_format_to_header

class TestUtils(object):

    def test_extract_and_format_to_header(self):
        input_str = '"Anete Gludīte" <john.doe@example.com>'
        expected_output = 'Anete Gludīte <john.doe@example.com>'
        assert utils.extract_and_format_to_header(input_str) == expected_output

    def test_extract_and_format_to_header_invalid_format(self):
        input_str = 'Anete Gludīte <john.doe@example.com>'
        with self.assertRaises(ValueError):
            utils.extract_and_format_to_header(input_str)
