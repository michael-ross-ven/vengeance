
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


def print_runtime(f=None):

    def runtime_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            tic  = default_timer()
            retv = _f_(*args, **kwargs)
            toc  = default_timer()
            elapsed = -(tic - toc)

            vengeance_message('@{}: {}'.format(function_name(_f_),
                                               format_seconds(elapsed)))
            return retv

        return functools_wrapper

    if f is None:
        return runtime_wrapper
    else:
        return runtime_wrapper(f)


def print_performance(f=None, *, repeat=3):

    def performance_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            retv  = None
            best  = None
            total = 0.0

            functools_repeat = functools.partial(itertools.repeat, None)
            was_gc_enabled   = gc.isenabled()
            gc.disable()

            for _ in functools_repeat(repeat):
                tic  = default_timer() * 1000
                retv = _f_(*args, **kwargs)
                toc  = default_timer() * 1000

                elapsed = -(tic - toc)
                total  += elapsed

                if best is None:
                    best = elapsed
                else:
                    best = min(best, elapsed)

            vengeance_message('@{}'
                              '\n\t\taverage: {}'
                              '\n\t\tbest:    {}'
                              .format(function_name(_f_),
                                      format_milliseconds(total / repeat),
                                      format_milliseconds(best)))

            if was_gc_enabled:
                gc.enable()

            return retv

        return functools_wrapper

    if f is None:
        return performance_wrapper
    else:
        return performance_wrapper(f)


def deprecated(message='deprecated'):

    def deprecated_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            _message_ = message.replace('"', "'")
            _message_ = '@{}: "{}"'.format(function_name(_f_), _message_)

            vengeance_warning(_message_,
                              DeprecationWarning,
                              stacklevel=3,
                              stack_frame=None)

            return _f_(*args, **kwargs)

        return functools_wrapper

    return deprecated_wrapper


def vengeance_warning(message,
                      category=Warning,
                      stacklevel=3,
                      stack_frame=None):

    import inspect
    import traceback
    import warnings

    # region {closure functions}
    if stack_frame is None:
        stack_frame = traceback.extract_stack(inspect.currentframe(), limit=stacklevel)[0]

    def format_warning(_message_, *_):
        nonlocal stack_frame

        w_s = ('\tν: <{w_type}> {w_message}'
               '\n\tν: File "{filename}", line {lineno}'
               '\n\n'.format(w_type=object_name(category),
                             w_message=_message_,
                             filename=stack_frame.filename,
                             lineno=stack_frame.lineno))
        return w_s
    # endregion

    original_format_warning = warnings.formatwarning

    warnings.formatwarning = format_warning
    warnings.warn(message,
                  category,
                  stacklevel)
    warnings.formatwarning = original_format_warning


def vengeance_message(s, printed=True):
    vs = '\tν: {}'.format(s)
    if printed:
        print_unicode(vs)

    return vs


def print_unicode(s):
    # region {closure functions}
    def convert_unicode(_s_):
        _s_ = (_s_.replace('ν', 'v')
                  .replace('μ', 'u'))
        _s_ = (_s_.encode('ascii', errors='backslashreplace')
                  .decode('ascii'))
        return _s_
    # endregion

    try:
        print(s)
    except UnicodeEncodeError:
        print(convert_unicode(s))


def format_seconds(secs):
    return format_milliseconds(secs * 1000)


def format_milliseconds(ms):
    ns  = ms * 1000000
    mis = ms * 1000
    s   = ms / 1000

    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    if d >= 1:
        f = '{:.0f} days, {:.0f} hours'.format(d, h)
    elif h >= 1:
        f = '{:.0f} hours, {:.0f} minutes'.format(h, m)
    elif m >= 1:
        f = '{:.0f} minutes, {:.0f} seconds'.format(m, s)
    elif s >= 1:
        f = '{:.2f} seconds'.format(s)
    elif ms >= 1:
        f = '{:.0f} ms'.format(ms)
    elif ms >= 0.1:
        f = '{:.2f} ms'.format(ms)
    elif mis >= 1:
        f = '{:.0f} μs'.format(mis)
    else:
        f = '{:.0f} ns'.format(ns)

    return f


def function_name(f):
    name = f.__qualname__
    if '.' in name:
        return name

    modulename = f.__module__.split('.')[-1]
    return '{}.{}'.format(modulename, name)


def object_name(o):
    try:
        return o.__name__
    except AttributeError:
        return o.__class__.__name__


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
        return o.isoformat()

    if isinstance(o, set):
        return list(o)

    raise TypeError('cannot convert type to json ' + repr(o))






