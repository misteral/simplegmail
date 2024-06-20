import unittest
from gmsa.utils import extract_and_format_to_header

class TestUtils(unittest.TestCase):

    def test_extract_and_format_to_header(self):
        input_str = '"John Doe" <john.doe@example.com>'
        expected_output = 'John Doe <john.doe@example.com>'
        self.assertEqual(extract_and_format_to_header(input_str), expected_output)

    def test_extract_and_format_to_header_invalid_format(self):
        input_str = 'John Doe <john.doe@example.com>'
        with self.assertRaises(ValueError):
            extract_and_format_to_header(input_str)

if __name__ == '__main__':
    unittest.main()
