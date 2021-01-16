
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
    __vengeance_prefix__ = '\tν: '    # nu: chr(957)
else:
    __vengeance_prefix__ = '\tv: '    # ascii


def print_runtime(f):

    def runtime_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            tic  = default_timer()
            retv = _f_(*args, **kwargs)
            toc  = default_timer()
            elapsed = -(tic - toc)

            s = '@{}: {}'.format(function_name(_f_), format_seconds(elapsed))
            s = vengeance_message(s)
            print(s)

            return retv

        return functools_wrapper

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

                # best  = elapsed if (best is None)  else min(best, elapsed)
                # worst = elapsed if (worst is None) else max(worst, elapsed)

                if best is None:
                    best = elapsed
                else:
                    best = min(best, elapsed)

                if worst is None:
                    worst = elapsed
                else:
                    worst = max(worst, elapsed)

            s = ('@{}'
                 '\n        best:    {}'
                 '\n        average: {}'
                 '\n        worst:   {}'
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


def styled(message,
           color='dark magenta',
           effect='bold'):

    # region {escape codes}
    effect_codes = {'bold':      '\x1b[1m',
                    'italic':    '\x1b[3m',
                    'underline': '\x1b[4m',
                    'end':       '\x1b[0m',
                    '':          '',
                    None:        ''}
    color_codes = {'grey':           '\x1b[29m',
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
                   'dark magenta':   '\x1b[38;2;170;50;130m',
                   '':               '',
                   None:             ''}
    # endregion

    if color not in color_codes:
        raise KeyError('invalid color: {}'.format(color))
    if effect not in effect_codes:
        raise KeyError('invalid style: {}'.format(effect))

    if is_tty_console:          # TTY console doesn't support ascii escapes
        return message

    styled_message = ('{ascii_color}{effect_start}{message}{effect_end}'
                       .format(ascii_color=color_codes[color],
                               effect_start=effect_codes[effect],
                               message=message,
                               effect_end=effect_codes['end']))
    return styled_message


def vengeance_message(message):
    return __vengeance_prefix__ + message


def deprecated(message='deprecated'):

    def deprecated_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):
            _message_ = "@{}: '{}'".format(function_name(_f_), message)
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
    import warnings

    # region {closure functions}
    if isinstance(stacklevel, int) and stackframe is None:
        import inspect
        import traceback
        stackframe = traceback.extract_stack(inspect.currentframe(), limit=stacklevel)[0]

    def vengeance_formatwarning(*_, **__):
        nonlocal stackframe
        nonlocal category
        nonlocal message

        aligned_indent = len(__vengeance_prefix__.replace('\t', ''))
        aligned_indent = ' ' * aligned_indent
        aligned_indent = '\t' + aligned_indent

        w_category = object_name(category)
        w_message  = message.replace('\n', '\n' + aligned_indent)

        line_1 = '<{}> {}'.format(w_category, w_message)
        if stackframe is None:
            line_2 = 'File {unknown}, line {unknown}'
        else:
            line_2 = 'File "{}", line {}'.format(stackframe.filename, stackframe.lineno)

        line_1 = vengeance_message(line_1)
        line_2 = aligned_indent + line_2
        w_message = '{}\n{}\n'.format(line_1, line_2)

        # w_message = styled(w_message, 'yellow', 'bold')

        return w_message
    # endregion

    original_formatwarning = warnings.formatwarning

    warnings.formatwarning = vengeance_formatwarning
    warnings.warn(message)
    warnings.formatwarning = original_formatwarning

    # print(end='')
    # import sys
    # sys.stdout.flush()
    # sys.stderr.flush()


def format_vengeance_header(n):
    return '⟪{}⟫'.format(n)


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


# def json_dumps_extended(o, indent=4, ensure_ascii=False):
def json_dumps_extended(o, **kwargs):
    kwargs['ensure_ascii'] = kwargs.get('ensure_ascii', False)
    kwargs['indent']       = kwargs.get('indent', 4)
    kwargs['default']      = kwargs.get('default', json_unhandled_conversion)

    if ultrajson_installed:
        del kwargs['default']

    return json.dumps(o, **kwargs)


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

