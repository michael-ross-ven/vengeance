
import re
from collections import Iterable

from functools import lru_cache

from datetime import date
from datetime import datetime
from datetime import timedelta

from dateutil.parser import parse as dateutil_parse


def to_datetime(v, d_format=None):
    """ convert variety of date representations into a datetime object
    :param v:
        an iterable, excel serial date, datetime, or string

    :param d_format:
        optional datetime.strptime format
    """

    if isinstance(v, str):
        d_ret = __parse_string(v, d_format)
    elif isinstance(v, float):
        d_ret = __parse_date_float(v)
        if d_ret is None:
            d_ret = __parse_excel_serial(v)
    elif isinstance(v, datetime):
        d_ret = v
    elif type(v) == date:
        d_ret = __date_to_datetime(v)
    elif isinstance(v, Iterable):
        d_ret = [to_datetime(d, d_format) for d in v]
    else:
        raise ValueError("invalid date: '{}', dont know how to convert '{}' instance".format(v, type(v)))

    return d_ret


def attempt_to_datetime(v):
    try:
        v = to_datetime(v)
        b = True
    except (ValueError, AttributeError):
        b = False

    return v, b


def is_valid_date(v):
    try:
        to_datetime(v)
        return True
    except (ValueError, AttributeError):
        return False


def excel_epoch():
    """ rnumber of days since 1900-01-01 """
    return datetime(1899, 12, 31)


def __parse_date_float(f):
    s = str(int(f))
    d_ret = __datetime_ymd(s)

    return d_ret


def __datetime_ymd(s):
    try:
        y, m, d = (int(s[:4]),
                   int(s[4:6]),
                   int(s[6:8]))
        return datetime(y, m, d)

    except ValueError:
        return None


def __parse_excel_serial(f):
    num_days = int(f) - 1
    return excel_epoch() + timedelta(days=num_days)


@lru_cache(maxsize=2**13)
def __parse_string(s, d_format):
    """
    time_fragment_re
        for cases like: '2017/01/01 00:00:00 000'
        these extra digits after the '00:00:00' value will break most parsers
        and should be removed
        eg:
            ' 000' = time_fragment_re.search('2017/01/01 00:00:00 000')
    """
    time_fragment_re = re.compile(r'''
        [\s][\d]{3,}$
    ''', re.X | re.I)

    s = s.strip()
    s = time_fragment_re.sub('', s)

    d_ret = __parse_string_strptime(s, d_format)
    if d_ret is None:
        d_ret = __parse_string_dateutil(s)

    return d_ret


def __parse_string_strptime(s, d_format):
    if d_format is not None:
        return datetime.strptime(s, d_format)

    # has hh:mm value, strptime not set up to handle timestamps
    if ':' in s:
        return None

    common_formats = ('%m/%d/%Y',       # 01/01/2001
                      '%Y-%m-%d',       # 2000-01-01
                      '%Y-%b-%d',       # 2000-jan-01
                      '%d-%b-%Y',       # 01-jan-2000
                      '%Y%m%d')         # 20000101

    for d_fmt in common_formats:
        try:
            return datetime.strptime(s, d_fmt)
        except ValueError:
            pass

    return None


def __parse_string_dateutil(s):
    try:
        return dateutil_parse(s)
    except ValueError:
        return None


def __date_to_datetime(date_t):
    return datetime(date_t.year, date_t.month, date_t.day)

