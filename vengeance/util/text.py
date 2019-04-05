
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


def print_timeit(f, *, repeat=3, number=1000):
    """
    stolen and modified from
    https://github.com/realpython/materials/blob/master/pandas-fast-flexible-intuitive/tutorial/timer.py

    Decorator: prints time from best of `repeat` trials.

    Mimics `timeit.repeat()`, but avg. time is printed.
    Returns function result and prints time.

    You can decorate with or without parentheses, as in
    Python's @dataclass class decorator.

    kwargs are passed to `print()`.
    """
    import gc
    import functools
    import itertools

    _repeat = functools.partial(itertools.repeat, None)

    def wrap(func):

        @functools.wraps(func)
        def performance_wrapper(*args, **kwargs):
            # Temporarily turn off garbage collection during the timing.
            # Makes independent timings more comparable.
            # If it was originally enabled, switch it back on afterwards.
            gcold = gc.isenabled()
            gc.disable()

            result = None

            try:
                # Outer loop - the number of repeats.
                trials = []
                for _ in _repeat(repeat):
                    # Inner loop - the number of calls within each repeat.
                    total = 0
                    for _ in _repeat(number):
                        start = default_timer()
                        result = func(*args, **kwargs)
                        end = default_timer()
                        total += end - start

                    trials.append(total)

                # We want the *average time* from the *best* trial.
                # For more on this methodology, see the docs for
                # Python's `timeit` module.
                #
                # "In a typical case, the lowest value gives a lower bound
                # for how fast your machine can run the given code snippet;
                # higher values in the result vector are typically not
                # caused by variability in Python’s speed, but by other
                # processes interfering with your timing accuracy."
                best = min(trials) / number

                print("Best of {} trials with {} function calls per trial:"
                      .format(repeat, number))
                print("Function `{}` ran in average of {:0.3f} seconds."
                      .format(func.__name__, best), end="\n\n")
            finally:
                if gcold:
                    gc.enable()

            return result

        return performance_wrapper

    # Syntax trick from Python @dataclass
    return wrap(f)


def repr_(sequence, concat=', ', quotes=False, wrap=None):
    """ extend formatting options of built-in repr() """

    def repr_recurse(v):
        if isinstance(v, Iterable) and not isinstance(v, str):
            c = ', '
            w = None

            if is_top_sequence_dict:
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

    is_top_sequence_dict = isinstance(sequence, dict)
    if is_top_sequence_dict:
        sequence = sequence.items()

    s = concat.join(repr_recurse(o) for o in sequence)

    if wrap:
        s = wrap[0] + s + wrap[1]

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


