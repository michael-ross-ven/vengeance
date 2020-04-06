
import gc
import itertools
import functools

from datetime import date
from timeit import default_timer

from ..conditional import ultrajson_installed

if ultrajson_installed:
    import ujson as json
else:
    import json


def print_runtime(f):

    def runtime_wrapper(_f_):
        @functools.wraps(f)
        def functools_wrapper(*args, **kwargs):
            tic = default_timer() * 1000
            ret = _f_(*args, **kwargs)
            toc = default_timer() * 1000

            elapsed = -(tic - toc)
            print_unicode('\tτ: @{}: {}'.format(function_name(_f_),
                                                format_milliseconds(elapsed)))
            return ret

        return functools_wrapper

    return runtime_wrapper(f)


def print_performance(f=None, *, repeat=3):

    functools_repeat = functools.partial(itertools.repeat, None)

    def performance_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            was_gc_enabled = gc.isenabled()
            gc.disable()

            ret  = None
            best = None
            total = 0.0

            try:
                for _ in functools_repeat(repeat):
                    tic = default_timer() * 1000
                    ret = _f_(*args, **kwargs)
                    toc = default_timer() * 1000

                    elapsed = -(tic - toc)
                    total += elapsed

                    if best is None:
                        best = elapsed
                    else:
                        best = min(best, elapsed)

                print_unicode('\tτ: @{}\n\t\t'
                              'average:   {}\n\t\t'
                              'best:      {}\n'
                              .format(function_name(_f_),
                                      format_milliseconds(total / repeat),
                                      format_milliseconds(best)))
            finally:
                if was_gc_enabled:
                    gc.enable()

            return ret
        return functools_wrapper

    if f is None:
        return performance_wrapper
    else:
        return performance_wrapper(f)


def format_milliseconds(ms):
    if ms <= 0.001:
        return '{:.0f} ns'.format(ms * 1000000)
    if ms <= 0.01:
        return '{:.2f} μs'.format(ms * 1000)
    if ms <= 1:
        return '{:.3f} ms'.format(ms)
    if ms <= 10:
        return '{:.1f} ms'.format(ms)

    m, s = divmod(ms / 1000, 60)
    h, m = divmod(m, 60)

    if h >= 1:
        f = '{} hour {} min'.format(h, m)
    elif m >= 1:
        f = '{} min {} sec'.format(int(m), int(s))
    elif s >= 1:
        f = '{:.2f} sec'.format(s)
    else:
        f = '{:.0f} ms'.format(ms)

    return f


def function_name(f):
    name = f.__qualname__
    if '.' in name:
        return name

    modulename = f.__module__.split('.')[-1]
    return '{}.{}'.format(modulename, name)


def json_dumps_extended(o, indent=4, ensure_ascii=False):
    if ultrajson_installed:
        return json.dumps(o, indent=indent)

    s = json.dumps(o,
                   indent=indent,
                   default=json_unhandled_conversion,
                   ensure_ascii=ensure_ascii)

    return s


def json_unhandled_conversion(o):
    """
    json can not convert certain python objects to
    string representations like dates, sets, etc
    """
    if isinstance(o, date):
        # return o.timestamp() ?
        return o.isoformat()

    if isinstance(o, set):
        return list(o)

    raise TypeError('cannot convert type to json ' + repr(o))


def vengeance_message(s):
    print_unicode('\tν: {}'.format(s))


def print_unicode(s):
    try:
        print(s)
    except UnicodeEncodeError:
        s = _replace_greek_characters(s)
        s = (s.encode('ascii', errors='backslashreplace')
              .decode('ascii'))

        print(s)


def _replace_greek_characters(s):
    greek_chars = {'α': 'a',
                   'β': 'b',
                   'ε': 'e',
                   'τ': 't',
                   'μ': 'u',
                   'ν': 'v'}

    for old, new in greek_chars.items():
        s = s.replace(old, new)

    return s


