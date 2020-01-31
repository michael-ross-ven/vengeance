
from functools import lru_cache

from datetime import date
from datetime import datetime
from datetime import timedelta

from dateutil.parser import parse as dateutil_parse


def to_datetime(v, d_format=None):
    """
    :param v:
        value to be converted
    :param d_format:
        datetime.strptime format
    """
    if isinstance(v, str) or d_format is not None:
        date_time = parse_date_string(v, d_format)
    elif isinstance(v, float):
        date_time = parse_date_float(v) or parse_date_excel_serial(v)
    elif isinstance(v, datetime):
        date_time = v
    elif type(v) == date:
        date_time = datetime(v.year, v.month, v.day)
    elif isinstance(v, (list, tuple)):
        date_time = [to_datetime(d, d_format) for d in v]
    else:
        raise ValueError("can't convert '{}' instance to datetime".format(type(v)))

    return date_time


def is_date(v):
    """ :return: (bool successful, converted value) """
    try:
        return True, to_datetime(v)
    except ValueError:
        return False, v


@lru_cache(maxsize=2**13)
def parse_date_float(f):
    s = str(int(f))

    try:
        y, m, d = (int(s[:4]),
                   int(s[4:6]),
                   int(s[6:8]))

        return datetime(y, m, d)
    except ValueError:
        return None


@lru_cache(maxsize=2**13)
def parse_date_excel_serial(f):
    """ number of days since 1900-01-01 """
    excel_epoch = datetime(1900, 1, 1)
    return excel_epoch + timedelta(days=int(f))


@lru_cache(maxsize=2**13)
def parse_date_string(s, d_format):
    s = s.strip()

    if d_format is not None:
        return datetime.strptime(s, d_format)

    date_time = __parse_date_strptime(s)
    if date_time is None:
        date_time = dateutil_parse(s)

    return date_time


def __parse_date_strptime(s):
    common_formats = ('%m-%d-%Y',  # 01-01-2000
                      '%m/%d/%Y',  # 01/01/2000
                      '%Y-%m-%d',  # 2000-01-01
                      '%Y/%m/%d',  # 2000/01/01
                      '%Y-%b-%d',  # 2000-jan-01
                      '%d-%b-%Y',  # 01-jan-2000
                      '%Y%m%d')    # 20000101

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

