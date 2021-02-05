
import gc
import itertools
import functools

from datetime import date
from timeit import default_timer

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

    @functools.wraps(f)
    def runtime_wrapper(*args, **kwargs):
        tic  = default_timer()
        retv = f(*args, **kwargs)
        toc  = default_timer()
        elapsed = -(tic - toc)

        s = '@{}: {}'.format(function_name(f), format_seconds(elapsed))
        s = vengeance_message(s)
        print(s)

        return retv

    return runtime_wrapper


def print_performance(f=None, repeat=5):

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
                tic  = default_timer()
                retv = _f_(*args, **kwargs)
                toc  = default_timer()
                elapsed = -(tic - toc)

                total += elapsed

                if best is None:
                    best = elapsed
                else:
                    best = min(best, elapsed)

                if worst is None:
                    worst = elapsed
                else:
                    worst = max(worst, elapsed)

            s = ('@{}, {}'
                 '\n        {}best:    {}'
                 '\n        {}average: {}'
                 '\n        {}worst:   {}'
                 .format(function_name(_f_),
                         format_header_lite(str(repeat) + ' trials'),
                         styled('★★★ ', 'blue'),    format_seconds(best),
                         styled('★★   ', 'blue'), format_seconds(total / repeat),
                         styled('★    ', 'blue'),    format_seconds(worst)))
            s = vengeance_message(s)
            print(s)

            if was_gc_enabled:
                gc.enable()

            return retv

        return functools_wrapper

    if isinstance(f, int):
        f, repeat = None, f

    if callable(f):
        return performance_wrapper(f)
    else:
        return performance_wrapper


def deprecated(f=None, message='deprecated'):

    def deprecated_wrapper(_f_):
        @functools.wraps(_f_)
        def functools_wrapper(*args, **kwargs):

            # noinspection PyTypeChecker
            vengeance_warning("@{}: '{}'".format(function_name(_f_), message),
                              DeprecationWarning,
                              stacklevel=None,
                              color='grey',
                              effect='bold')

            return _f_(*args, **kwargs)

        return functools_wrapper

    if isinstance(f, str):
        f, message = None, f

    if callable(f):
        return deprecated_wrapper(f)
    else:
        return deprecated_wrapper


def vengeance_warning(message,
                      category=Warning,
                      stacklevel=2,
                      stackframe=None,
                      color=None,
                      effect=None):

    import inspect
    import traceback
    import warnings

    # region {closure functions}
    aligned_indent = ' ' * len(__vengeance_prefix__.replace('\t', ''))
    aligned_indent = '\t' + aligned_indent

    def first_non_vengeance_frame():
        nonlocal stackframe

        is_found = False
        tb_stack = reversed(traceback.extract_stack())

        for i, stackframe in enumerate(tb_stack):
            if '\\vengeance\\' not in stackframe.filename:
                is_found = True
                break

        if not is_found:
            stackframe = traceback.extract_stack(inspect.currentframe(), limit=2)[0]

    def extract_frame():
        nonlocal stackframe

        sl = max(stacklevel, 2)
        stackframe = traceback.extract_stack(inspect.currentframe(), limit=sl)[0]

    def vengeance_formatwarning(*_, **__):
        line_1 = message.replace('\n', '\n' + aligned_indent)
        line_1 = '<{}> {}'.format(object_name(category), line_1)
        line_1 = vengeance_message(line_1)

        line_2 = 'File "{}", line {}'.format(filename, lineno)
        line_2 = aligned_indent + line_2

        w_message = ('{}\n{}\n'.format(line_1, line_2)
                               .replace('\t', '    '))
        if color or effect:
            w_message = styled(w_message, color, effect)

        return w_message
    # endregion

    if stacklevel is None and stackframe is None:
        first_non_vengeance_frame()
    elif isinstance(stacklevel, int) and stackframe is None:
        extract_frame()

    if stackframe is not None:
        filename = stackframe.filename
        lineno   = stackframe.lineno
    else:
        filename = '{unknown}'
        lineno   = '{unknown}'

    original_formatwarning = warnings.formatwarning
    warnings.formatwarning = vengeance_formatwarning
    warnings.warn(message)
    warnings.formatwarning = original_formatwarning

    print(end='')


def styled(message,
           color='grey',
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

    if not is_utf_console:
        return message
    if not color and not effect:
        return message

    effect_style = color_codes[color] + effect_codes[effect]
    effect_end   = effect_codes['end']
    message      = str(message).replace(effect_end, effect_style)

    return ('{effect_style}{message}{effect_end}'
            .format(effect_style=effect_style,
                    message=message,
                    effect_end=effect_end))


def vengeance_message(message):
    return __vengeance_prefix__ + message


def format_header(h=''):
    return '⟪{}⟫'.format(h)


def format_header_lite(h=''):
    return '⟨{}⟩'.format(h)


def format_integer(i):
    """ eg: '1_000_000' = format_integer(1000000) """
    return '{:,}'.format(int(i)).replace(',', '_')


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
        f_ms = '{:.1f} sec'.format(s)
    elif ms >= 1:
        f_ms = '{:.1f} ms'.format(ms)
    elif us >= 1:
        if is_utf_console:
            f_ms = '{:.0f} μs'.format(us)
        else:
            f_ms = '{:.0f} mcs'.format(us)
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
    # if isinstance(v, Decimal) ?

    raise TypeError("Object of type '{}' is not JSON serializable".format(object_name(v)))

