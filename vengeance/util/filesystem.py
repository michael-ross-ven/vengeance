
import _pickle as cpickle
import csv
import gc
import os
import pprint
import shutil

from collections import namedtuple
from datetime import datetime
from json import JSONDecodeError
from glob import glob
from string import ascii_lowercase

from .text import json_unhandled_conversion

from .. conditional import ultrajson_installed
if ultrajson_installed:
    import ujson as json
else:
    import json

pickle_extensions = {'.flux', '.pkl', '.pickle'}
notimplemented_extensions = {'.7z',
                             '.gzip',
                             '.png',
                             '.jpg',
                             '.jpeg',
                             '.gif',
                             '.pdf'}


def read_file(path,
              encoding=None,
              mode='r',
              *,
              filetype=None,
              fkwargs=None):

    if mode[0] != 'r' or mode[-1] == '+':
        raise ValueError('invalid read mode: {}'.format(mode))

    filetype = __validate_filetype(filetype, path)
    as_bytes = __validate_mode_with_encoding(mode, encoding, filetype)
    mode     = __validate_mode_with_filetype(as_bytes, mode, filetype)
    fkwargs  = fkwargs or {}

    was_gc_enabled = gc.isenabled()
    gc.disable()

    if filetype == '.csv':
        fkwargs['nrows']  = fkwargs.get('nrows')
        fkwargs['strict'] = fkwargs.get('strict', True)

        nrows = fkwargs.pop('nrows')

        with open(path, mode, encoding=encoding) as f:
            data = csv.reader(f, **fkwargs)
            if isinstance(nrows, int):
                data = __read_limited_csv_rows(nrows, data)
            else:
                data = list(data)

    elif filetype == '.json':
        with open(path, mode, encoding=encoding) as f:
            try:
                data = json.load(f, **fkwargs)
            except (JSONDecodeError, ValueError) as e:
                raise ValueError('invalid encoding or malformed json: '
                                 '\n\tpath: {}'
                                 '\n\tencoding: {}'.format(path, encoding)) from e

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            data = cpickle.load(f, **fkwargs)

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
               mode='w',
               *,
               filetype=None,
               fkwargs=None):

    if not mode[0] in ('w', 'a'):
        raise ValueError('invalid write mode: {}'.format(mode))

    filetype = __validate_filetype(filetype, path)
    as_bytes = __validate_mode_with_encoding(mode, encoding, filetype)
    mode     = __validate_mode_with_filetype(as_bytes, mode, filetype)
    fkwargs  = fkwargs or {}

    was_gc_enabled = gc.isenabled()
    gc.disable()

    if filetype == '.csv':
        fkwargs['strict']         = fkwargs.get('strict', True)
        fkwargs['lineterminator'] = fkwargs.get('lineterminator', '\n')

        with open(path, mode, encoding=encoding) as f:
            csv.writer(f, **fkwargs).writerows(data)

    elif filetype == '.json':
        ensure_ascii = (encoding in (None, 'ascii'))
        fkwargs['indent']       = fkwargs.get('indent', 4)
        fkwargs['ensure_ascii'] = fkwargs.get('ensure_ascii', ensure_ascii)
        fkwargs['default']      = fkwargs.get('default', json_unhandled_conversion)

        if ultrajson_installed:
            del fkwargs['default']

        with open(path, mode, encoding=encoding) as f:
            json.dump(data, f, **fkwargs)

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            cpickle.dump(data, f, **fkwargs)

    elif as_bytes:
        with open(path, mode) as f:
            f.write(data)

    else:
        if not isinstance(data, (str, bytes)):
            # f.write() is much faster than f.writelines()
            data = pprint.pformat(data, **fkwargs)
            data = data.replace("'", '"')

        with open(path, mode, encoding=encoding) as f:
            f.write(data)

    if was_gc_enabled:
        gc.enable()


def __validate_filetype(filetype, path):
    """ check for file types that require specialized io libraries / protocols """
    filetype = filetype or parse_file_extension(path, include_dot=True)
    filetype = filetype.lower().strip()

    if not filetype.startswith('.'):
        filetype = '.' + filetype

    if filetype.startswith('.xl') or filetype in notimplemented_extensions:
        raise NotImplementedError("file type not supported: '{}'".format(filetype))

    return filetype


def __validate_mode_with_encoding(mode, encoding, filetype):
    as_bytes = mode.replace('+', '').endswith('b')

    if as_bytes and encoding:
        raise ValueError('as bytes mode does not accept an encoding argument')

    if as_bytes and filetype == '.csv':
        raise ValueError('as bytes mode is incompatable with csv module')

    return as_bytes


def __validate_mode_with_filetype(as_bytes, mode, filetype):
    if not as_bytes and (filetype in pickle_extensions):
        if mode.endswith('+'):
            mode = mode[0] + 'b+'
        else:
            mode += 'b'

    return mode


def __read_limited_csv_rows(nrows, csv_reader):
    m = []
    for _ in range(nrows):
        try:
            m.append(next(csv_reader))
        except StopIteration:
            break

    if not m:
        m = [[]]

    return m


def clear_dir(filedir):
    filedir = standardize_dir(filedir, explicit_cwd=True)
    if not os.path.exists(filedir):
        return

    del_paths = [filedir + item for item in os.listdir(filedir)]
    del_paths.sort(reverse=True)

    for path in del_paths:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def copy_dir(s_dir, d_dir, ignore=None, dirs_exist_ok=False):
    """
    shutil.copytree will fail if shutil.rmtree hasn't finished deleting folder:
        PermissionError: [WinError 5] Access is denied
    """
    s_dir = standardize_dir(s_dir)
    d_dir = standardize_dir(d_dir)

    if ignore:
        if isinstance(ignore, str):
            ignore = (ignore,)
        elif isinstance(ignore, set):
            ignore = tuple(ignore)

        ignore = shutil.ignore_patterns(*ignore)

    if not dirs_exist_ok and os.path.exists(d_dir):
        shutil.rmtree(d_dir)

    shutil.copytree(src=s_dir, dst=d_dir,
                    ignore=ignore,
                    dirs_exist_ok=dirs_exist_ok)


def file_creation_datetime(path):
    unix_t = os.path.getctime(path)
    return datetime.fromtimestamp(unix_t)


def file_modified_datetime(path):
    unix_t = os.stat(path).st_mtime
    return datetime.fromtimestamp(unix_t)


def parse_path(path, pathsep='/', explicit_cwd=False):

    ParsedPath = namedtuple('ParsedPath', ('directory',
                                           'filename',
                                           'extension'))
    if os.path.isdir(path):
        filedir  = path
        filename = ''
    else:
        filedir, filename = os.path.split(path)

    filedir  = standardize_dir(filedir, pathsep, explicit_cwd)
    filename = standardize_file_name(filename)
    filename, extn = os.path.splitext(filename)

    parsed_path = ParsedPath(filedir, filename, extn)

    return parsed_path


def standardize_path(path, pathsep='/', explicit_cwd=False):
    filedir, filename, extn = parse_path(path, pathsep, explicit_cwd)

    return filedir + filename + extn


def standardize_dir(filedir, pathsep='/', explicit_cwd=False):

    is_filedir_empty = (filedir == '')
    if not explicit_cwd and is_filedir_empty:
        return filedir

    if is_filedir_empty:
        filedir = os.getcwd()

    filedir = (filedir.replace('\\', pathsep)
                      .replace('/', pathsep)
                      .lower()
                      .strip())

    if not filedir.endswith(pathsep):
        filedir += pathsep

    drive_letters = ('{}:{}'.format(c, pathsep) for c in ascii_lowercase)

    for drive_letter in drive_letters:
        if filedir.startswith(drive_letter):
            filedir = filedir.replace(drive_letter, drive_letter.upper(), 1)
            break

    return filedir


def standardize_file_name(filename):
    return filename.lower().strip()


def parse_file_extension(filename, include_dot=True):
    filename = standardize_file_name(filename)
    _, extn = os.path.splitext(filename)

    if include_dot is False:
        extn = extn.replace('.', '', 1)

    return extn


def validate_path_exists(path):
    filedir, filename, extn = parse_path(path, pathsep='/', explicit_cwd=True)

    if not os.path.exists(filedir):
        raise FileNotFoundError('directory not found: \n\t{}'.format(filedir))

    path = filedir + filename + extn

    if not os.path.exists(path):
        glob_paths = glob(filedir + filename + '.*')
        if glob_paths:
            extn = parse_file_extension(os.path.split(glob_paths[0])[1], include_dot=True)
            raise FileNotFoundError('file extension not found: '
                                    '\n\t{}'
                                    '\n\t{}'
                                    '\n\tdid you mean: {}?'.format(filedir, filename, extn))

        raise FileNotFoundError('file not found: '
                                '\n\t{}'
                                '\n\t{}'.format(filedir, filename + extn))

    return path




