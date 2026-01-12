# mail_handler_mailcom.py
"""
Wrapper for existing mail.com handler to provide a consistent function name
used by the rest of the codebase.
"""
from mail_handler import get_code_from_mail as _get_code_from_mail


def get_code_from_mailcom(driver, email, password):
    """Call existing mail.com handler."""
    return _get_code_from_mail(driver, email, password)
