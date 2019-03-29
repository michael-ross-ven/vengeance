
import json

from timeit import default_timer
from datetime import date
from collections import Iterable

nbsp = chr(160)
nonstandard_chars = "\"\'\n\t" + nbsp


def print_runtime(f):

    def runtime_wrapper(*args, **kwargs):
        f_name = f.__module__.split('.')[-1]
        f_name = '{}.{}'.format(f_name, f.__name__)

        tic = default_timer() * 1000

        if kwargs:
            result = f(*args, **kwargs)
        elif args:
            result = f(*args)
        else:
            result = f()

        toc = default_timer() * 1000
        elapsed = -(tic - toc)

        print_unicode('   τ: @{}: {}'.format(f_name, format_ms(elapsed)))

        return result

    return runtime_wrapper


def format_ms(ms):
    m, s = divmod(ms / 1000, 60)
    h, m = divmod(m, 60)

    if h >= 1:
        f_ms = '{} hr {} min'.format(h, m)
    elif m >= 1:
        f_ms = '{} min {} sec'.format(int(m), int(s))
    elif s > 1:
        f_ms = '{:.2f} sec'.format(s)
    elif ms > 10:
        f_ms = '{} ms'.format(int(ms))
    elif ms > 1:
        f_ms = '{:.1f} ms'.format(ms)
    else:
        f_ms = '{:.2f} us'.format(int(ms * 1000))

    return f_ms


def repr_(sequence, concat=', ', quotes=False, wrap=None):
    """ extend formatting options of built-in repr() """

    def repr_recurse(v):
        if isinstance(v, Iterable) and not isinstance(v, str):
            c = ', '
            w = None

            if is_original_seq_dict:
                c = ': '
            elif isinstance(v, dict):
                w = '{}'
            elif isinstance(v, tuple):
                w = '()'
            elif isinstance(v, list):
                w = '[]'

            return repr_(v, c, wrap=w)

        if isinstance(v, str) and quotes:
            return "'{}'".format(v)

        return str(v)

    is_original_seq_dict = isinstance(sequence, dict)
    if is_original_seq_dict:
        sequence = sequence.items()

    s = [repr_recurse(o) for o in sequence]

    if wrap:
        s = concat.join(s)
    else:
        s = wrap[0] + concat.join(s) + wrap[1]

    return s


def sanitize(v):
    s = value_to_string(v)
    s = remove_multiple(s, nonstandard_chars)
    s = s.strip()

    return s


def value_to_string(v):
    if isinstance(v, str):
        return v

    if v is None:
        v = ''
    elif isinstance(v, date):
        v = v.strftime('%Y-%m-%d')
    else:
        v = str(v)

    return v


def remove_multiple(s, substrs, first_only=False):
    for sub in substrs:
        if first_only:
            s = s.replace(sub, '', 1)
        else:
            s = s.replace(sub, '')

    return s


def between(s, substr_1, substr_2=None):
    """ text between inner and outer substrings (exclusive)
    eg:
        'ell' = between('hello', 'h', 'o')
    """
    if substr_2 is None:
        substr_2 = substr_1

    i_1 = s.index(substr_1) + len(substr_1)
    i_2 = s.index(substr_2, i_1)

    return s[i_1:i_2]


def p_json_dumps(o, indent=4):
    """
    json can not convert certain python objects to string representations
        dates
        sets
    """
    def unhandled_conversion(_o):
        if isinstance(_o, date):
            return _o.isoformat()

        if isinstance(_o, set):
            return list(_o)

        raise TypeError('cannot convert type to json ' + repr(_o))

    return json.dumps(o, indent=indent,  default=unhandled_conversion)


def to_ascii(s):
    greek_chrs = {'α': 'a',
                  'β': 'b',
                  'ε': 'e',
                  'τ': 't',
                  'ν': 'v'}

    s = str(s)
    for old, new in greek_chrs.items():
        s = s.replace(old, new)

    s = (s.encode('ascii', errors='backslashreplace')
          .decode('ascii'))

    return s


def print_unicode(s):
    try:
        print(s)
    except UnicodeEncodeError:
        print(to_ascii(s))


def vengeance_message(s):
    print_unicode('   ν: {}'.format(s))


