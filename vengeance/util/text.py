
import re
import json

from timeit import default_timer
from datetime import date
from collections import Iterable


def print_runtime(f):
    def runtime_wrapper(*args, **kwargs):
        tic = default_timer() * 1000
        ret = f(*args, **kwargs)
        toc = default_timer() * 1000

        elapsed = -(tic - toc)
        print_unicode('\tτ: @{}: {}'.format(function_name(f),
                                            format_ms(elapsed)))

        return ret

    return runtime_wrapper


def print_performance(f=None, *, repeat=3):
    """
    stolen and modified from
    https://github.com/realpython/materials/blob/master/pandas-fast-flexible-intuitive/tutorial/timer.py
    """
    import gc
    import functools
    import itertools

    functools_repeat = functools.partial(itertools.repeat, None)

    def performance_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            was_gc_enabled = gc.isenabled()
            gc.disable()

            ret   = None
            best  = None
            total = 0

            try:
                for _ in functools_repeat(repeat):
                    tic = default_timer() * 1000
                    ret = _f_(*args, **kwargs)
                    toc = default_timer() * 1000

                    elapsed = -(tic - toc)
                    if best is None:
                        best = elapsed
                    else:
                        best = min(best, elapsed)

                    total += elapsed

                average = total / repeat
                print_unicode('\tτ: @{}'
                              '\n\t\taverage:   {}'
                              '\n\t\tbest:      {}\n'
                              .format(function_name(_f_), format_ms(average), format_ms(best)))
            finally:
                if was_gc_enabled:
                    gc.enable()

            return ret
        return functools_wrapper

    if f is None:
        return performance_wrapper
    else:
        return performance_wrapper(f)


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


def function_name(f):
    return '{}.{}'.format(f.__module__.split('.')[-1], f.__name__)


def repr_(sequence, concat=', ', quotes=False, wrap=True):
    """ extend formatting options beyond built-in repr() """

    def repr_recurse(v):
        if isinstance(v, str):
            if quotes:
                v = "'{}'".format(v)

            return v

        if is_sequence_dict:
            c = ': '
            w = False

            return repr_(v, c, quotes, w)

        if isinstance(v, Iterable):
            c = ', '
            w = wrap

            return repr_(v, c, quotes, w)

        return str(v)

    def wrapped_characters(v):
        if isinstance(v, dict):
            w = '{}'
        elif isinstance(v, tuple):
            w = '()'
        elif isinstance(v, list):
            w = '[]'
        else:
            w = None

        return w

    if wrap is True:
        w_ = wrapped_characters(sequence)
    else:
        w_ = wrap

    is_sequence_dict = isinstance(sequence, dict)
    if is_sequence_dict:
        sequence = sequence.items()

    s = concat.join(repr_recurse(o) for o in sequence)

    if w_:
        s = w_[0] + s + w_[1]

    return s


def sanitize(v):
    """
    convert value to string and remove common characters that can make
    string more difficult to work with (quotes and whitespace)

    (the html non-breaking space (&nbsp) is particularly annoying, but dealt
    with by the regex whitespace character class)
    """
    non_standard_re = re.compile(r'[\"\'\s]+')

    s = value_to_string(v)
    s = non_standard_re.sub('', s).strip()

    return s


def value_to_string(v):
    if v is None:
        return ''

    return str(v)


def remove_multiple(s, substrs, first_only=False):
    if s == '':
        return s

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


def p_json_dumps(o, indent=4, ensure_ascii=False):
    """
    json can not convert certain python objects to
    string representations like dates, sets, etc
    """
    def unhandled_conversion(_o_):
        if isinstance(_o_, date):
            return _o_.isoformat()

        if isinstance(_o_, set):
            return list(_o_)

        raise TypeError('cannot convert type to json ' + repr(_o_))

    s = json.dumps(o, indent=indent, default=unhandled_conversion, ensure_ascii=ensure_ascii)

    return s


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
    print_unicode('\tν: {}'.format(s))



