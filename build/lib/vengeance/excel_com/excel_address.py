
import re

# for office 2010+
max_rows = 1048575           # 2**20
max_cols = 16384             # 2**14


def col_letter_offset(cs, offset):
    return col_letter(col_number(cs) + offset)


def col_letter(ci):
    """ column numbers to string """
    if isinstance(ci, str):
        return __validate_column_letter(ci)

    __validate_column_number(ci)

    cs = ''
    while ci > 0:
        ci_2 = ((ci - 1) % 26)
        cs   = chr(ci_2 + 65) + cs
        ci   = (ci - ci_2) // 26

    return cs


def col_number(cs):
    """ column letters to integer """
    if isinstance(cs, (float, int)):
        return __validate_column_number(int(cs))

    cs = __validate_column_letter(cs)

    ci = 0
    for i, ci_2 in enumerate(cs, 1):
        ci_2 = ord(ci_2) - 64
        ci  += ci_2 * 26**(len(cs) - i)

    __validate_column_number(ci)

    return ci


def __validate_column_letter(cs):
    cs = str(cs).upper()

    if not re.search('^[a-z]{1,3}$', cs, re.I):
        raise ValueError("'{}' is not a valid Excel column address "
                         "\n(valid columns should be 'A - {}')".format(cs, col_letter(max_cols)))

    return cs


def __validate_column_number(ci):
    if ci < 1:
        raise ValueError("column number ({:,}) must be >= 1".format(ci))

    if ci > max_cols:
        raise ValueError("column number ({:,}) exceeds Excel's maximum column limit".format(ci))

    return ci
