
from datetime import date
from datetime import datetime
from datetime import timedelta

from .classes.parsed_time_cls import parsed_time_cls
from ..conditional import dateutil_installed

if dateutil_installed:
    from dateutil.parser import parse as dateutil_parse

excel_epoch = datetime(1900, 1, 1)


def to_datetime(v, d_format=None):
    """
    :param v:        value to be converted
    :param d_format: datetime.strptime format
    """
    if isinstance(v, str):
        date_time = parse_date_string(v, d_format)
    elif isinstance(v, (int, float)):
        date_time = (parse_date_unix_timestamp(v) or
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


def attempt_to_datetime(v, d_format=None):
    """ :return: (bool success, converted value) """
    try:
        return True, to_datetime(v, d_format)
    except (ValueError, TypeError):
        return False, v


def parse_timedelta(td):
    if not hasattr(td, 'total_seconds'):
        raise AttributeError('timedelta must have a ".total_seconds()" method')

    return parse_seconds(td.total_seconds())


def parse_seconds(total_seconds):
    parsed_time = parsed_time_cls(total_seconds)
    return parsed_time


def parse_date_unix_timestamp(v):
    """ eg:
        datetime.datetime(2000, 1, 1, 0, 0) = parse_date_unix_timestamp(946702800)
    """
    try:
        return datetime.fromtimestamp(v)
    except ValueError:
        return None


def parse_date_excel_serial(v):
    """ number of days since 1900-01-01 """
    try:
        return excel_epoch + timedelta(days=v)
    except ValueError:
        return None


def to_excel_serial(v):
    v = to_datetime(v)
    return (v - excel_epoch).days


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

