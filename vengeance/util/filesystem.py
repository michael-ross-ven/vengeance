
import csv
import gc
import re
import os
import pprint
import shutil

from io import StringIO
from urllib.request import urlopen
from urllib.parse import urlparse
from collections import namedtuple
from datetime import datetime
from glob import glob
from pathlib import Path

from . text import json_unhandled_conversion
from .. conditional import cpickle
from .. conditional import ultrajson_installed

if ultrajson_installed:
    import ujson as json
else:
    import json

pickle_extensions = {'.flux', '.pkl', '.pickle'}


def read_file(path,
              encoding=None,
              mode='r',
              filetype=None,
              **kwargs):

    path, filetype, mode, as_bytes_mode, kwargs = __validate_read_write_params(
                                                  path, encoding, mode, filetype, kwargs, 'read')

    was_gc_enabled = gc.isenabled()
    gc.disable()

    if filetype == '.csv':
        data = __read_csv(path, mode, encoding, kwargs)

    elif filetype == '.json':
        data = __read_json(path, mode, encoding, kwargs)

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            data = cpickle.load(f, **kwargs)

    elif as_bytes_mode:
        with open(path, mode) as f:
            data = f.read()

    else:
        if __is_path_a_url(path):
            raise NotImplementedError

        with open(path, mode, encoding=encoding) as f:
            data = f.read()

    if was_gc_enabled:
        gc.enable()

    return data


# noinspection DuplicatedCode
def write_file(path,
               data,
               encoding=None,
               mode='w',
               filetype=None,
               **kwargs):

    path, filetype, mode, as_bytes_mode, kwargs = __validate_read_write_params(
                                                  path, encoding, mode, filetype, kwargs, 'write')
    was_gc_enabled = gc.isenabled()
    gc.disable()

    if filetype == '.csv':
        try:             newline = kwargs.pop('newline')
        except KeyError: newline = ''

        with open(path, mode, encoding=encoding, newline=newline) as f:
            csv.writer(f, **kwargs).writerows(data)

    elif filetype == '.json':
        kwargs['ensure_ascii'] = kwargs.get('ensure_ascii', encoding in (None, 'ascii'))
        kwargs['indent']       = kwargs.get('indent', 4)
        kwargs['default']      = kwargs.get('default', json_unhandled_conversion)
        if ultrajson_installed:
            del kwargs['default']

        with open(path, mode, encoding=encoding) as f:
            json.dump(data, f, **kwargs)

    elif filetype in pickle_extensions:
        with open(path, mode) as f:
            cpickle.dump(data, f, **kwargs)

    elif as_bytes_mode:
        with open(path, mode) as f:
            f.write(data)

    else:
        if not isinstance(data, str):
            data = pprint.pformat(data, **kwargs)

        with open(path, mode, encoding=encoding) as f:
            f.write(data)

    if was_gc_enabled:
        gc.enable()


def __validate_read_write_params(path,
                                 encoding,
                                 mode,
                                 filetype,
                                 kwargs,
                                 read_or_write):

    as_bytes_mode = ('b' in mode)

    path          = __validate_path(path)
    filetype      = __validate_filetype(filetype, path)
    as_bytes_mode = __validate_mode_with_encoding(as_bytes_mode, encoding, filetype)
    mode          = __validate_mode_with_filetype(as_bytes_mode, mode, filetype)
    mode          = __validate_mode(mode, read_or_write)
    kwargs        = __validate_file_keyword_args(kwargs)

    as_bytes_mode = ('b' in mode)

    is_url = __is_path_a_url(path)

    if read_or_write == 'read' and is_url:
        if filetype not in ('.csv', '.json') or as_bytes_mode:
            raise NotImplementedError('read from url not handled for filetype: {}'.format(filetype))
    elif read_or_write == 'write' and is_url:
        raise NotImplementedError('can not write to url: {}'.format(path))

    return (path,
            filetype,
            mode,
            as_bytes_mode,
            kwargs)


def __validate_path(path):
    if isinstance(path, str):
        return path
    if isinstance(path, Path):
        return str(path)

    raise TypeError('invalid type for path: {}'.format(path))


def __validate_filetype(filetype, path):
    """ check for file types that require specialized io libraries / protocols """
    notimplemented_extensions = {'.7z',
                                 '.gzip',
                                 '.png',
                                 '.jpg',
                                 '.jpeg',
                                 '.gif',
                                 '.pdf'}

    filetype = filetype or parse_file_extension(path, include_dot=True)
    filetype = filetype.lower().strip()

    if not filetype.startswith('.'):
        filetype = '.' + filetype

    if filetype.startswith('.xl') or filetype in notimplemented_extensions:
        raise NotImplementedError("file type not supported: '{}'".format(filetype))

    return filetype


def __validate_mode_with_encoding(as_bytes_mode, encoding, filetype):
    if as_bytes_mode and encoding:
        raise ValueError('as bytes mode does not accept an encoding argument')
    if encoding and filetype in pickle_extensions:
        raise ValueError('pickle module does not accept an encoding argument')
    if as_bytes_mode and filetype == '.csv':
        raise ValueError('as bytes mode is incompatable with csv module')

    return as_bytes_mode


def __validate_mode_with_filetype(as_bytes_mode, mode, filetype):
    if not as_bytes_mode and (filetype in pickle_extensions):
        if mode.endswith('+'):
            mode = mode[0] + 'b+'
        else:
            mode += 'b'

    return mode


def __validate_mode(mode, read_or_write):
    if read_or_write == 'read':
        if mode[0] not in ('r',) or mode.endswith('+'):
            raise ValueError('invalid read mode: {}'.format(mode))

    elif read_or_write == 'write':
        if mode[0] not in ('w', 'a'):
            raise ValueError('invalid write mode: {}'.format(mode))

    else:
        raise ValueError("invalid read_write_type: {}, read_write_type must be in ('read', 'write')"
                         .format(read_or_write))

    return mode


def __validate_file_keyword_args(kwargs):
    kwargs = kwargs or {}

    if 'kwargs' in kwargs:
        kwargs.update(kwargs.pop('kwargs'))

    return kwargs


def __read_csv(path, mode, encoding, kwargs):
    """
    _csv.Error: new-line character seen in unquoted field - do you need to open the file in universal-newline mode?
        fixed by passing lineterminator='\r'
        or newline='\r', newline=''
    """
    # region {closure}
    def read_csv_rows():
        if nrows is None:
            return list(csv_reader)

        m = []
        try:
            for _ in range(nrows):
                m.append(next(csv_reader))
        except StopIteration:
            pass

        return m

    def remove_url_from_rows(m):
        try:
            while __is_path_a_url(m[0][0]):
                del m[0]

                if nrows is not None:
                    try:
                        m.append(next(csv_reader))
                    except StopIteration:
                        break
        except IndexError:
            pass

        return m
    # endregion

    if encoding is None:
        encoding = 'ascii'

    try:             nrows = kwargs.pop('nrows')
    except KeyError: nrows = None

    try:             newline = kwargs.pop('newline')
    except KeyError: newline = ''

    if __is_path_a_url(path):
        with StringIO(__url_request(path, encoding=encoding), newline=newline) as f:
            csv_reader = csv.reader(f, **kwargs)
            return remove_url_from_rows(read_csv_rows())

    with open(path, mode, encoding=encoding, newline=newline) as f:
        csv_reader = csv.reader(f, **kwargs)
        return read_csv_rows()


def __read_json(path, mode, encoding, kwargs):
    if (encoding is None) and ('b' not in mode):
        encoding = 'ascii'

    if __is_path_a_url(path):
        return json.loads(__url_request(path, encoding=encoding), **kwargs)

    with open(path, mode, encoding=encoding) as f:
        return json.load(f, **kwargs)


def __is_path_a_url(path):
    if not isinstance(path, str):
        return False

    return bool(urlparse(path).netloc)


def __url_request(url, encoding=None):

    with urlopen(url) as request:
        if request.code != 200:
            raise IOError('bad request: ({}) {}'.format(request.code, url))

        byte_string = request.read()
        if encoding:
            return byte_string.decode(encoding)
        else:
            return byte_string


def clear_dir(filedir):
    filedir = standardize_dir(filedir, explicit_cwd=True)

    if not os.path.exists(filedir):
        return

    if not os.path.isdir(filedir):
        raise TypeError('"{}" is not a directory'.format(filedir))

    for item in os.listdir(filedir):
        path = filedir + item

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

    shutil.copytree(src=s_dir,
                    dst=d_dir,
                    ignore=ignore,
                    dirs_exist_ok=dirs_exist_ok)


def file_creation_datetime(path):
    unix_t = os.path.getctime(path)
    return datetime.fromtimestamp(unix_t)


def file_modified_datetime(path):
    unix_t = os.stat(path).st_mtime
    return datetime.fromtimestamp(unix_t)


def parse_path(path,
               pathsep='/',
               explicit_cwd=False):

    ParsedPath = namedtuple('ParsedPath', ('directory',
                                           'filename',
                                           'extension'))
    path = (str(path).replace('"', '')
                     .replace("'", ''))
    if os.path.isdir(path):
        filedir   = path
        filename  = ''
        extension = ''
    else:
        filedir,  filename  = os.path.split(path)
        filename, extension = os.path.splitext(filename)

    filedir = standardize_dir(filedir, pathsep, explicit_cwd)

    return ParsedPath(filedir, filename, extension)


def parse_file_extension(filename, include_dot=True):
    _, extension = os.path.splitext(str(filename))
    if (include_dot is False) and extension.startswith('.'):
        extension = extension[1:]

    return extension


def standardize_path(path,
                     pathsep='/',
                     explicit_cwd=False):

    p_path = parse_path(path, pathsep, explicit_cwd)
    path   = ''.join(p_path)

    return path


def standardize_dir(filedir,
                    pathsep='/',
                    explicit_cwd=False):

    if (explicit_cwd is False) and (filedir == ''):
        return filedir

    filedir = filedir or os.getcwd()
    filedir = (filedir.replace('"', '')
                      .replace("'", '')
                      .replace('\\', pathsep)
                      .replace('/', pathsep))

    if not filedir.endswith(pathsep):
        filedir += pathsep

    if re.search(r'^[a-z][:][/\\]', filedir):
        filedir = filedir[0].upper() + filedir[1:]

    return filedir


def validate_path_exists(path):

    (filedir,
     filename,
     extension) = parse_path(path, explicit_cwd=True)

    if not os.path.exists(filedir):
        raise FileNotFoundError('directory not found: \n\t{}'.format(filedir))

    path = filedir + filename + extension

    if not os.path.exists(path):
        glob_paths = glob(filedir + filename + '.*')
        if glob_paths:

            extension = parse_file_extension(os.path.split(glob_paths[0])[1], include_dot=True)
            raise FileNotFoundError('file extension not found: '
                                    '\n\t{}'
                                    '\n\t{}'
                                    '\n\tdid you mean: {}?'.format(filedir, filename, extension))

        raise FileNotFoundError('file not found: '
                                '\n\t{}'
                                '\n\t{}'.format(filedir, filename + extension))

    return path




