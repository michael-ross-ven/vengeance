
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


def print_performance(f=None, *, repeat=3, number=100):
    """
    stolen and modified from
    https://github.com/realpython/materials/blob/master/pandas-fast-flexible-intuitive/tutorial/timer.py

    Decorator: prints time from best of repeat trials.

    Mimics timeit.repeat(), but avg. time is printed.
    Returns function result and prints time.

    You can decorate with or without parentheses, as in
    Python's @dataclass class decorator.
    """
    import gc
    import functools
    import itertools

    _repeat = functools.partial(itertools.repeat, None)

    def wrap(func):
        @functools.wraps(func)
        def performance_wrapper(*args, **kwargs):

            # Temporarily turn off garbage collection
            gcold = gc.isenabled()
            gc.disable()

            result = None
            best   = None
            total  = 0

            try:
                for _ in _repeat(repeat):
                    total = 0

                    for _ in _repeat(number):                   # number of trials within each repeat.
                        tic = default_timer() * 1000
                        result = func(*args, **kwargs)
                        toc = default_timer() * 1000
                        elapsed = -(tic - toc)

                        if best is None:
                            best = elapsed
                        else:
                            best = min(best, elapsed)

                        total += elapsed

                average = total / number

                f_name = func.__module__.split('.')[-1]
                f_name = '{}.{}'.format(f_name, func.__name__)

                print_unicode('   τ: @{}: {} (average), {} (best)'.format(f_name,
                                                                          format_ms(average),
                                                                          format_ms(best),))

            finally:
                if gcold:
                    gc.enable()

            return result

        return performance_wrapper

    if f is None:
        return wrap
    else:
        return wrap(f)


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


def p_json_dumps(o, indent=4, ensure_ascii=False):
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

    s = json.dumps(o, indent=indent,  default=unhandled_conversion, ensure_ascii=ensure_ascii)

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
    print_unicode('   ν: {}'.format(s))


