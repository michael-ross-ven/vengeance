
import _pickle as cpickle       # cPickle was renamed as pickle in python3
import csv
import gc
import os
import shutil

from datetime import datetime
from glob import glob
from .text import json_unhandled_conversion
from ..conditional import ultrajson_installed

if ultrajson_installed:
    import ujson as json
else:
    import json

binary_extensions = {'.flux', '.bin', '.pkl', '.pickle'}


def read_file(path,
              encoding=None,
              fkwargs=None,
              mode='r'):

    as_bytes = mode.endswith('b')
    extn     = file_extension(path, include_dot=True)
    kw       = fkwargs or {}

    __validate_extension(extn)
    __validate_encoding(as_bytes, encoding, extn)

    was_gc_enabled = gc.isenabled()
    gc.disable()

    if extn == '.csv':
        kw['strict'] = kw.get('strict', True)

        with open(path, mode, encoding=encoding) as f:
            data = list(csv.reader(f, **kw))

    elif extn == '.json':
        with open(path, mode, encoding=encoding) as f:
            data = json.load(f, **kw)

    elif extn in binary_extensions:
        if not as_bytes: mode += 'b'

        with open(path, mode) as f:
            data = cpickle.load(f, **kw)

    elif as_bytes:
        with open(path, mode) as f:
            data = f.read()
    else:
        with open(path, mode, encoding=encoding) as f:
            data = f.read()

    if was_gc_enabled:
        gc.enable()

    return data


def write_file(path,
               data,
               encoding=None,
               fkwargs=None,
               mode='w'):

    as_bytes = mode.endswith('b')
    extn     = file_extension(path, include_dot=True)
    kw       = fkwargs or {}

    __validate_extension(extn)
    __validate_encoding(as_bytes, encoding, extn)

    was_gc_enabled = gc.isenabled()
    gc.disable()

    if extn == '.csv':
        kw['strict'] = kw.get('strict', True)
        kw['lineterminator'] = kw.get('lineterminator', '\n')

        with open(path, mode, encoding=encoding) as f:
            csv.writer(f, **kw).writerows(data)

    elif extn == '.json':
        if not ultrajson_installed:
            # need a way of passing indent to json_unhandled_conversion
            kw['indent']  = kw.get('indent', 4)
            kw['default'] = kw.get('default', json_unhandled_conversion)

        with open(path, mode, encoding=encoding) as f:
            json.dump(data, f, **kw)

    elif extn in binary_extensions:
        if not as_bytes: mode += 'b'

        with open(path, mode) as f:
            cpickle.dump(data, f, **kw)

    else:
        if as_bytes:
            with open(path, mode) as f:
                f.write(data)
        else:
            # v.write() is faster than v.writelines()
            if not isinstance(data, str):
                data = '\n'.join([str(v) for v in data])

            with open(path, mode, encoding=encoding) as f:
                f.write(data)

    if was_gc_enabled:
        gc.enable()


def __validate_extension(extn):
    """ check for file types that require specialized io libraries / protocols """
    if extn.startswith('.xl') or extn in {'.7z', '.gzip'}:
        raise NotImplementedError("'{}' file type not supported".format(extn))


def __validate_encoding(as_bytes, encoding, extn):
    if as_bytes and encoding:
        raise ValueError('as bytes mode does not accept an encoding argument')

    if as_bytes and extn == '.csv':
        raise ValueError('as bytes mode is incompatable with csv module')


def clear_dir(filedir):
    if not os.path.exists(filedir):
        return

    filedir = standardize_dir(filedir)
    for item in os.listdir(filedir):
        path = filedir + item
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copy_dir(s_dir, d_dir, exclude_dirs=None):
    exclude_dirs = exclude_dirs or set()

    s_dir = standardize_dir(s_dir)
    d_dir = standardize_dir(d_dir)

    if not os.path.exists(d_dir):
        os.makedirs(d_dir)

    for file_content in os.listdir(s_dir):
        if file_content in exclude_dirs:
            continue

        s_path = s_dir + file_content
        d_path = d_dir + file_content

        if os.path.isdir(s_path):
            shutil.copytree(src=s_path, dst=d_path)
        else:
            shutil.copy(src=s_path, dst=d_path)


def file_creation_date(path):
    unix_t = os.path.getctime(path)
    return datetime.fromtimestamp(unix_t)


def file_last_modified(path):
    unix_t = os.stat(path).st_mtime
    return datetime.fromtimestamp(unix_t)


def standardize_dir(filedir, pathsep='/'):
    """
    pathsep=os.path.sep?
    """
    filedir = (filedir.replace('\\', pathsep)
                      .replace('/', pathsep)
                      .lower()
                      .strip())

    if filedir != '' and not filedir.endswith(pathsep):
        filedir += pathsep

    return filedir


def standardize_file_name(filename):
    return filename.lower().strip()


def standardize_path(path, pathsep='/'):
    filedir, filename = parse_path(path)

    filedir  = standardize_dir(filedir, pathsep)
    filename = standardize_file_name(filename)

    return filedir + filename


def sanatize_file_name(filename):
    """ replace illegal Windows file name characters with '-'

    (there's an additional set of path characters that are
     illegal only for Windows' .zip compression)
    """
    invalid_chrs = {'\\': '-',
                    '/':  '-',
                    ':':  '-',
                    '*':  '-',
                    '?':  '-',
                    '<':  '-',
                    '>':  '-',
                    '|':  '-',
                    '"':  '-'}

    for k, v in invalid_chrs.items():
        filename = filename.replace(k, v)

    return filename


def assert_path_exists(path):
    filedir, filename = parse_path(path)

    if filedir != '' and not os.path.exists(filedir):
        raise FileNotFoundError("invalid directory: '{}'".format(filedir))

    if not os.path.exists(path):
        extn  = file_extension(filename, include_dot=True)
        retry = filename.replace(extn, '.*')
        path  = glob(standardize_dir(filedir) + retry)

        if path:
            msg = "invalid file extension".format(extn)
        else:
            msg = "'{}' not found within directory '{}'".format(filename, filedir)

        raise FileNotFoundError(msg)


def parse_path(path):

    if os.path.isdir(path):
        filedir  = path
        filename = ''
    else:
        filedir, filename = os.path.split(path)

    return filedir, filename


def file_extension(filename, include_dot=True):
    _, extn = os.path.splitext(filename)
    if include_dot is False:
        extn = extn.replace('.', '')

    extn = extn.lower().strip()

    return extn


def apply_file_extension(filename, extn):
    if not extn.startswith('.'):
        extn = '.' + extn

    if filename.endswith(extn):
        return filename

    return filename + extn


