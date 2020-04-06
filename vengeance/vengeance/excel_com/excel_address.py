
import re

max_rows    = 1048575
max_cols    = 16384             # maximum number of columns in an excel worksheet (office 2010)
max_str_len = 32767             # largest string that will fit in a single cell


def col_letter_offset(col_str, offset):
    return col_letter(col_number(col_str) + offset)


def col_letter(col_int):
    """ convert column numbers to character representation """
    if isinstance(col_int, str):
        __assert_valid_column_letter(col_int)
        return col_int

    __assert_valid_column_number(col_int)

    col_str = ''
    while col_int > 0:
        c = (col_int - 1) % 26
        col_str = chr(c + 65) + col_str
        col_int = (col_int - c) // 26

    return col_str


def col_number(col_str):
    """ convert column letters to int representation """
    if col_str == '' or col_str is None:
        return 0

    if isinstance(col_str, (float, int)):
        col_int = int(col_str)
        __assert_valid_column_number(col_int)
        return col_int

    __assert_valid_column_letter(col_str)

    col_int = 0
    col_str = col_str.upper()

    for i, c in enumerate(col_str, 1):
        p = len(col_str) - i
        c = ord(c) - 64
        col_int += c * 26**p

    __assert_valid_column_number(col_int)

    return col_int


def __assert_valid_column_letter(col_str):
    col_re = re.compile('^[a-z]{1,3}$', re.I)

    if not col_re.match(col_str):
        raise ValueError("'{}' is not a valid Excel column address"
                         "\n(valid columns should be 'A - {}')"
                         .format(col_str.upper(), col_letter(max_cols)))


def __assert_valid_column_number(col_int):
    if col_int > max_cols:
        raise ValueError("column number ({:,}) exceeds Excel's maximum column limit"
                         .format(col_int))

