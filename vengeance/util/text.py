
import gc
import itertools
import functools

from datetime import date
from timeit import default_timer

from ..conditional import is_tty_console
from ..conditional import is_utf_console
from ..conditional import ultrajson_installed

if ultrajson_installed:
    import ujson as json
else:
    import json

if is_utf_console:
    __vengeance_character__ = 'ν'       # utf nu: chr(957)
else:
    __vengeance_character__ = 'v'


def print_runtime(f=None):

    def runtime_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            tic  = default_timer()
            retv = _f_(*args, **kwargs)
            toc  = default_timer()
            elapsed = -(tic - toc)

            print(vengeance_message('@{}: {}'.format(function_name(_f_),
                                                     format_seconds(elapsed))))
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
            worst = None
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

                if worst is None:
                    worst = elapsed
                else:
                    worst = max(worst, elapsed)

            s = ('@{}'
                 '\n\t\tbest:    {}'
                 '\n\t\taverage: {}'
                 '\n\t\tworst:   {}'
                 .format(function_name(_f_),
                         format_milliseconds(best),
                         format_milliseconds(total / repeat),
                         format_milliseconds(worst)))
            s = vengeance_message(s)

            print(s)

            if was_gc_enabled:
                gc.enable()

            return retv

        return functools_wrapper

    if f is None:
        return performance_wrapper
    else:
        return performance_wrapper(f)


# noinspection DuplicatedCode
def styled(message,
           color_style=None,
           text_style=None):

    ascii_escapes = {'bold':           '\x1b[1m',       # effects
                     'italic':         '\x1b[3m',
                     'underline':      '\x1b[4m',
                     'grey':           '\x1b[29m',      # colors
                     'white':          '\x1b[30m',
                     'red':            '\x1b[31m',
                     'orange':         '\x1b[32m',
                     'yellow':         '\x1b[33m',
                     'blue':           '\x1b[34m',
                     'magenta':        '\x1b[35m',
                     'green':          '\x1b[36m',
                     'bronze':         '\x1b[37m',
                     'bright red':     '\x1b[91m',
                     'bright yellow':  '\x1b[93m',
                     'bright magenta': '\x1b[95m',
                     'bright cyan':    '\x1b[96m',
                     'end':            '\x1b[0m',       # misc
                     '':               '',
                     None:             ''}

    if color_style not in ascii_escapes:
        raise KeyError('invalid color: {}'.format(color_style))
    if text_style not in ascii_escapes:
        raise KeyError('invalid style: {}'.format(text_style))

    # TTY console doesn't support ascii escapes
    if is_tty_console:
        return message

    styled_message = ('{ascii_color}{effect_start}{message}{effect_end}'
                       .format(ascii_color=ascii_escapes[color_style],
                               effect_start=ascii_escapes[text_style],
                               message=message,
                               effect_end=ascii_escapes['end']))
    return styled_message


def vengeance_message(message):
    return '\t{}: {}'.format(__vengeance_character__,
                             message)


def print_u(message):
    try:
        print(message)
    except UnicodeEncodeError:
        print(unicode_to_ascii(message))


def unicode_to_ascii(message):
    return (message.encode('ascii', errors='backslashreplace')
                   .decode('ascii'))


def deprecated(message='deprecated'):

    def deprecated_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            _message_ = '@{}():  "{}"'.format(function_name(_f_), message)

            vengeance_warning(_message_,
                              DeprecationWarning,
                              stacklevel=3,
                              stackframe=None)

            return _f_(*args, **kwargs)

        return functools_wrapper

    return deprecated_wrapper


def vengeance_warning(message,
                      category=Warning,
                      stacklevel=2,
                      stackframe=None):
    import inspect
    import sys
    import traceback
    import warnings

    # region {closure functions}
    if stacklevel is None:
        fileloc = ''
    elif stackframe is None:
        stackframe = traceback.extract_stack(inspect.currentframe(), limit=stacklevel)[0]
        fileloc = '\n\t{vc}: File "{filename}", line {lineno}'.format(vc=__vengeance_character__,
                                                                      filename=stackframe.filename,
                                                                      lineno=stackframe.lineno)

    def vengeance_formatwarning(*_, **__):
        nonlocal category
        nonlocal message
        nonlocal fileloc

        w_category = object_name(category)
        w_message  = message.replace('"', '').replace('\n', '\n\t   ')

        w_s = ('\t{vc}: <{w_category}> {w_message}'
               '{fileloc}'
               '\n\n'.format(vc=__vengeance_character__,
                             w_category=w_category,
                             w_message=w_message,
                             fileloc=fileloc))
        return w_s
    # endregion

    original_formatwarning = warnings.formatwarning
    warnings.formatwarning = vengeance_formatwarning
    warnings.warn(message)
    warnings.formatwarning = original_formatwarning

    sys.stdout.flush()
    sys.stderr.flush()


def format_seconds(secs):
    return format_milliseconds(secs * 1000)


def format_milliseconds(ms):
    ns = ms * 1000000
    us = ms * 1000
    s  = ms / 1000

    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    if d >= 1:
        f_ms = '{:.0f}d {:.0f}h {:.0f}m'.format(d, h, m)
    elif h >= 1:
        f_ms = '{:.0f}h {:.0f}m {:.0f}s'.format(h, m, s)
    elif m >= 1:
        f_ms = '{:.0f}m {:.0f}s'.format(m, s)
    elif s >= 1:
        f_ms = '{:.2f} seconds'.format(s)
    elif ms >= 1:
        f_ms = '{:.1f} ms'.format(ms)
    elif us >= 1:
        if is_utf_console:
            f_ms = '{:.0f} μs'.format(us)
        else:
            f_ms = '{:.0f} mi s'.format(us)
    else:
        f_ms = '{:.0f} ns'.format(ns)

    return f_ms


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
    """ if ultrajson not installed, use json_unhandled_conversion() as default function  """
    if ultrajson_installed:
        return json.dumps(o,
                          indent=indent,
                          ensure_ascii=ensure_ascii)
    else:
        return json.dumps(o,
                          indent=indent,
                          ensure_ascii=ensure_ascii,
                          default=json_unhandled_conversion)


def json_unhandled_conversion(v):
    """
    convert certain python objects to json string representations, eg:
        date, datetime, set
    """
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, set):
        return list(v)

    raise TypeError("Object of type '{}' is not JSON serializable".format(object_name(v)))

