import re
from email.utils import formataddr
from email.header import Header

def extract_and_format_to_header(input_str):
    # Regular expression to extract name and email
    match = re.match(r'"?([^"]+)"? <(.+)>', input_str)
    if not match:
        raise ValueError(f"Input string: {input_str} is not in the correct format")

    recipient_name, recipient_email = match.groups()

    # Properly format the "To" header
    to_header = formataddr((str(Header(recipient_name, 'utf-8')), recipient_email))

    return to_header
