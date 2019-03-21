
import re
from functools import lru_cache

from datetime import date
from datetime import datetime
from datetime import timedelta

from collections import Iterable


def to_datetime(v):
    """ convert variety of date representations into a datetime object
    :param v:
        an iterable, excel serial date, datetime, or string

    hmmmmmm, is this faster?
    from dateutil.parser import parse
    """

    if isinstance(v, datetime):
        d_ret = v
    elif type(v) == date:
        d_ret = __date_to_datetime(v)
    elif isinstance(v, float):
        d_ret = __parse_date_float(v)
        if d_ret is None:
            d_ret = __parse_excel_serial(v)
    elif isinstance(v, str):
        d_ret = __parse_string(v)
    elif isinstance(v, Iterable):
        d_ret = [to_datetime(d) for d in v]
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
def __parse_string(s):
    s = s.strip()

    d_ret = __parse_string_strptime(s)
    if d_ret is None:
        d_ret = __parse_string_pandas(s)

    return d_ret


def __parse_string_strptime(s):
    if ':' in s:
        # has hh:mm value, strptime has no chance at this
        return None

    common_formats = ('%Y-%m-%d', '%Y%m%d', '%m/%d/%Y')

    for d_fmt in common_formats:
        try:
            return datetime.strptime(s, d_fmt)
        except ValueError:
            pass

    return None


def __parse_string_pandas(s):
    """ let pandas library do the heavy lifting for parsing date strings

    time_fragment_re
        datetimes sometimes come formatted like '2017/01/01 00:00:00 000'
        which has an extra ' 000' fragment after the hh:mm:ss value
        these extra digits will break the pandas parser and should be removed
        eg:
            ' 000' = time_fragment_re.search('2017/01/01 00:00:00 000')
    """
    from pandas import to_datetime as pandas_to_datetime                # an expensive import (~3s)
    from pandas import NaT
    pandas_non_date = NaT.__class__

    # for cases like: '2017/01/01 00:00:00 000'
    time_fragment_re = re.compile(r'''
        [\s][\d]{3,}$
    ''', re.X | re.I)

    s = time_fragment_re.sub('', s)

    d_ret = pandas_to_datetime(s)
    d_ret = d_ret.to_pydatetime()
    if isinstance(d_ret, pandas_non_date):
        raise ValueError("invalid date, could not parse: '{}'".format(s))

    return d_ret


def __date_to_datetime(date_t):
    return datetime(date_t.year, date_t.month, date_t.day)

