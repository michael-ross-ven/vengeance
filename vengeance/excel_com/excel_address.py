
import re

col_re = re.compile('[a-z]{1,3}', re.I)

max_cols    = 16384             # maximum number of columns in an excel worksheet (office 2010)
max_str_len = 32767             # largest string that will fit in a single cell


def col_letter_offset(col_str, offset):
    return col_letter(col_number(col_str) + offset)


def col_letter(col_int):
    """ convert column numbers to character representation """
    if isinstance(col_int, str):
        __assert_valid_column_letter(col_int)
        return col_int

    if col_int > max_cols:
        raise ValueError('number: {:,} exceeds the maximum number of columns in excel'.format(col_int))

    col_str = ''
    while col_int > 0:
        c = (col_int - 1) % 26
        col_str = chr(c + 65) + col_str
        col_int = (col_int - c) // 26

    return col_str


def col_number(col_str):
    """ convert column letters to int representation """
    if isinstance(col_str, (float, int)):
        return int(col_str)

    if col_str == '':
        return 0

    __assert_valid_column_letter(col_str)

    col_int = 0
    col_str = col_str.upper()

    for i, c in enumerate(col_str, 1):
        p = len(col_str) - i
        c = ord(c) - 64
        col_int += c * 26**p

    return col_int


def __assert_valid_column_letter(col_str):
    if not col_re.match(col_str):
        raise ValueError("invalid excel column: '{}'".format(col_str))

