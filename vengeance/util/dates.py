
from collections import namedtuple
from datetime import date
from datetime import datetime
from datetime import timedelta
from functools import lru_cache
from math import trunc

from ..conditional import dateutil_installed

if dateutil_installed:
    from dateutil.parser import parse as dateutil_parse

# 2**15: cache ~32,800 days, or ~90 years
dates_cachesize = 2**15
excel_epoch     = datetime(1900, 1, 1)


def to_datetime(v, d_format=None):
    """
    :param v:        value to be converted
    :param d_format: datetime.strptime format
    """
    if isinstance(v, str):
        date_time = parse_date_string(v, d_format)
    elif isinstance(v, (int, float)):
        date_time = (parse_date_timestamp(v) or
                     parse_date_excel_serial(v) or
                     parse_date_numeric_string(v))

    elif isinstance(v, (list, tuple)):
        date_time = [to_datetime(d, d_format) for d in v]
    elif isinstance(v, datetime):
        date_time = v
    elif type(v) == date:
        date_time = datetime(v.year, v.month, v.day)
    else:
        raise TypeError("can't convert '{}' instance to datetime".format(type(v)))

    if date_time is None:
        raise ValueError("can't convert value: '{}' to datetime".format(v))

    return date_time


def parse_timedelta(td):
    if not isinstance(td, timedelta):
        raise TypeError('value must be instance of timedelta')

    return parse_seconds(td.total_seconds())


def parse_seconds(ts):
    if not isinstance(ts, (float, int)):
        raise TypeError('value must be instance of (float, int)')

    def truncate(n, precision=1):
        e = 10**precision
        return trunc(n * e) / e

    ParsedTime = namedtuple('ParsedTime', ('days',
                                           'hours',
                                           'minutes',
                                           'seconds',
                                           'microseconds'))
    s = abs(ts)

    us = (s % 1) * 1e6
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    s = int(s)
    m = int(m)
    h = int(h)
    d = int(d)

    if truncate(us % 1, 3) == 0.999:
        us = round(us, 3)
    elif truncate(us % 1, 4) == 0.000:
        us = round(us, 4)
    elif str(int(us)).endswith('9999'):
        us = round(us)

    is_negative = (ts < 0)

    if is_negative:
        us = -us if (us > 0.0) else 0.0
        s = -s if (s > 0.0) else 0
        h = -h if (h > 0.0) else 0
        m = -m if (m > 0.0) else 0
        d = -d if (d > 0.0) else 0

    return ParsedTime(d, h, m, s, us)


@lru_cache(maxsize=dates_cachesize)
def is_date(v):
    """ :return: (bool success, converted value) """
    try:
        return True, to_datetime(v)
    except (ValueError, TypeError):
        return False, v


@lru_cache(maxsize=dates_cachesize)
def parse_date_timestamp(v):
    """ eg:
        datetime.datetime(2000, 1, 1, 0, 0) = parse_date_timestamp(946702800.0)
    """
    try:
        return datetime.fromtimestamp(v)
    except ValueError:
        return None


@lru_cache(maxsize=dates_cachesize)
def parse_date_excel_serial(v):
    """ number of days since 1900-01-01 """
    try:
        return excel_epoch + timedelta(days=v)
    except ValueError:
        return None


def to_excel_serial(v):
    v = to_datetime(v)
    return (v - excel_epoch).days


@lru_cache(maxsize=dates_cachesize)
def parse_date_numeric_string(v):
    """ eg:
        datetime.datetime(2000, 12, 1, 0, 0) = parse_date_numeric(20001201)
    """
    s = str(v)
    if len(s) != 8:
        return None

    try:
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
        return datetime(y, m, d)
    except ValueError:
        return None


@lru_cache(maxsize=dates_cachesize)
def parse_date_string(s, d_format):
    if d_format is not None:
        return datetime.strptime(s, d_format)

    date_time = __parse_date_strptime(s)

    if date_time is None:
        date_time = __parse_date_dateutil(s)

    return date_time


def __parse_date_strptime(s):
    common_formats = ('%m-%d-%Y',       # 01-01-2000
                      '%m/%d/%Y',       # 01/01/2000
                      '%Y-%m-%d',       # 2000-01-01
                      '%Y/%m/%d',       # 2000/01/01
                      '%Y-%b-%d',       # 2000-Jan-01
                      '%d-%b-%Y',       # 01-Jan-2000
                      '%Y%m%d')         # 20000101

    if 'T' in s:
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None

    if not (__compatible_with_strptime_lengths(s, common_formats)):
        return None

    for d_format in common_formats:
        try:
            return datetime.strptime(s, d_format)
        except ValueError:
            pass

    return None


def __compatible_with_strptime_lengths(s, common_formats):
    _common_formats_ = [df.replace('%Y', '2000')
                          .replace('%m', '01')
                          .replace('%d', '01')
                          .replace('%b', 'jan') for df in common_formats]

    max_cf = max(len(cf) for cf in _common_formats_)
    min_cf = min(len(cf) for cf in _common_formats_) - 2
    len_s = len(s)

    return min_cf <= len_s <= max_cf


def __parse_date_dateutil(s):
    """
    from .text import vengeance_message
    print(vengeance_message("('python-dateutil' package not installed)"))
    """

    if not dateutil_installed:
        raise ImportError("'python-dateutil' package not installed")

    try:
        return dateutil_parse(s)
    except ValueError:
        return None

