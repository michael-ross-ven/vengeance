
import ctypes
from ctypes import POINTER
from ctypes import PyDLL
from ctypes import byref
from ctypes.wintypes import BOOL

import pythoncom
from comtypes import COMError
from comtypes import GUID
from comtypes import IUnknown
from comtypes.automation import IDispatch
from comtypes.client import CreateObject
from comtypes.client.dynamic import Dispatch

# noinspection PyUnresolvedReferences
from pythoncom import com_error

from win32com.client import Dispatch as pywin_dispatch                      # late-bound reference
# from win32com.client.gencache import EnsureDispatch as pywin_dispatch     # early-bound reference

from .excel_constants import xlMaximized
from ..util.filesystem import assert_path_exists
from ..util.filesystem import standardize_path
from ..util.text import vengeance_message

FindWindowEx               = ctypes.windll.user32.FindWindowExA
AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow

corrupt_hwnds = set()

# utf-encoded strings cause issues wtih C++ safearray strings in FindWindowEx()
xl_class_name   = 'XLMAIN'.encode('ascii')
xl_desk_class   = 'XLDESK'.encode('ascii')
xl_excel7_class = 'EXCEL7'.encode('ascii')
xl_clsid        = '{00020400-0000-0000-C000-000000000046}'
native_om       = -16


def open_workbook(path,
                  excel_instance=None,
                  *,
                  read_only=False,
                  update_links=True):

    print_extra_line = False

    wb = is_workbook_open(path)

    if wb is None:
        if excel_instance is None:
            excel_app = empty_excel_instance()
        elif excel_instance == 'any':
            excel_app = any_excel_instance()
        else:
            excel_app = excel_instance

        if excel_app is None:
            excel_app = new_excel_instance()
            print_extra_line = True

        wb = __workbook_from_excel_app(excel_app,
                                       path,
                                       update_links,
                                       read_only)

    elif excel_instance not in ('any', None):
        if wb.Application != excel_instance:
            vengeance_message("'{}' already open in another Excel instance".format(wb.Name))
            print_extra_line = True

    if wb.ReadOnly is False and read_only is True:
        vengeance_message("'{}' is NOT opened read-only".format(wb.Name))
        print_extra_line = True

    if wb.ReadOnly is True and read_only is False:
        vengeance_message("('{}' opened as read-only)".format(wb.Name))
        print_extra_line = True

    if print_extra_line:
        print()

    return wb


def is_workbook_open(path):
    """ scan all open workbooks across all Excel instances, match is determined by matching file paths

    :return captured Workbook or None
    """
    path = standardize_path(path)
    assert_path_exists(path)

    window_h = FindWindowEx(0, 0, xl_class_name, None)
    while window_h != 0:
        for wb in __workbooks_from_hwnd(window_h):
            if standardize_path(wb.FullName) == path:
                return wb

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    return None


# noinspection PyUnusedLocal
def close_workbook(wb, save):
    """
    this function accomplishes a few things that the client may not want to deal with
        * if Workbook is the last in the Excel application, closes the application as well

        * in order to correctly release com pointers, it needs to be completely de-referenced
          need to be severed for the pointer to be released
    """
    if save and wb.ReadOnly:
        raise AssertionError("workbook: '{}' is open read-only, cannot save and close".format(wb.Name))

    excel_app = wb.Application
    if save:
        wb.Save()
    else:
        excel_app.DisplayAlerts = False

    wb.Close()
    wb = None

    if save is False:
        excel_app.DisplayAlerts = True

    if excel_app.Workbooks.Count == 0:
        excel_app.Quit()
        excel_app = None


def new_excel_instance():
    excel_app = CreateObject('Excel.Application', dynamic=True)     # comtypes method
    excel_app = __comtype_to_pywin_obj(excel_app, IDispatch)
    excel_app = pywin_dispatch(excel_app)

    excel_app.WindowState = xlMaximized

    app_to_foreground(excel_app)
    reload_all_add_ins(excel_app)

    return excel_app


def empty_excel_instance():
    window_h = FindWindowEx(0, 0, xl_class_name, None)

    while window_h != 0:
        excel_app = __excel_app_from_hwnd(window_h)
        if __is_excel_app_empty(excel_app):
            vengeance_message('utilizing empty Excel instance ...')

            return excel_app

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    return None


def any_excel_instance():
    excel_app = pywin_dispatch('Excel.Application')
    if excel_app:
        excel_app.Visible = True

    return excel_app


def all_excel_instances():
    excel_apps = []
    window_h = FindWindowEx(0, 0, xl_class_name, None)

    while window_h != 0:
        excel_app = __excel_app_from_hwnd(window_h)
        if excel_app:
            excel_apps.append(excel_app)

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    return excel_apps


def reload_all_add_ins(excel_app):
    vengeance_message('reloading Excel add-ins...')

    for add_in in excel_app.AddIns:
        if add_in.Installed:
            name = add_in.Name
            try:
                add_in.Installed = False
                add_in.Installed = True
                print('\t   * {}'.format(name))
            except COMError:
                vengeance_message('failed to load add-in: {}' + name)


def app_to_foreground(excel_app):
    SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow

    excel_app.Visible = True
    SetForegroundWindow(excel_app.Hwnd)


def __is_excel_app_empty(excel_app):
    if excel_app is None:
        return False

    workbooks = list(excel_app.Workbooks)
    if not workbooks:
        excel_app.Visible = True
        return True

    if len(workbooks) == 1:
        wb = workbooks[0]

        if wb.Saved and wb.Name == 'Book1':
            ws = wb.Sheets[1]
            if ws.Name == 'Sheet1' and ws.UsedRange.Address == '$A$1':
                return True

    return False


def __workbook_from_excel_app(excel_app, path, update_links, read_only):
    assert_path_exists(path)

    if read_only:
        vengeance_message('opening workbook as read-only ...')

    excel_app.DisplayAlerts = False
    wb = excel_app.Workbooks.Open(path, update_links, read_only)
    excel_app.DisplayAlerts = True

    return wb


def __workbooks_from_hwnd(window_h):
    excel_app = __excel_app_from_hwnd(window_h)
    if excel_app is not None:
        return list(excel_app.Workbooks)
    else:
        return []


def __excel_app_from_hwnd(window_h):
    """
    the comtypes library is used to search windows handles for Excel application,
    then converts that pointer to a pywin object

    sometimes, non-Excel applications are running under the same window_h
    as an Excel process, like "print driver host for applications"
    these will fail to return a valid excel7_wnd for FindWindowEx

    xl_desk_class, xl_excel7_class


    Excel's clsid: found in HKEY_CLASSES_ROOT

    obj_ptr = POINTER(IDispatch)()
    IDispatch: expected type Type[_CT]?
    """
    global corrupt_hwnds

    if window_h in corrupt_hwnds:
        return None

    desk_wnd   = FindWindowEx(window_h, None, xl_desk_class, None)
    excel7_wnd = FindWindowEx(desk_wnd, None, xl_excel7_class, None)

    if excel7_wnd == 0:
        corrupt_hwnds.add(window_h)
        return None

    # noinspection PyTypeChecker
    obj_ptr = POINTER(IDispatch)()

    cls_id = GUID.from_progid(xl_clsid)
    AccessibleObjectFromWindow(excel7_wnd,
                               native_om,
                               byref(cls_id),
                               byref(obj_ptr))
    window = Dispatch(obj_ptr)

    try:
        com_ptr   = window.Application
        excel_app = __comtype_to_pywin_obj(com_ptr, IDispatch)
        excel_app = pywin_dispatch(excel_app)

        excel_app.Visible = True

        return excel_app

    except (COMError, com_error, NameError) as e:
        raise ChildProcessError('remote procedure call to Excel application rejected\n'
                                '(check if cursor is still active within a cell somewhere, '
                                'Excel will reject automation calls while waiting on '
                                'user input)') from e


def __comtype_to_pywin_obj(ptr, interface):
    """Convert a comtypes pointer 'ptr' into a pythoncom PyI<interface> object.

    'interface' specifies the interface we want; it must be a comtypes
    interface class.  The interface must be implemented by the object;
    and the interface must be known to pythoncom.
    """
    com_obj = PyDLL(pythoncom.__file__).PyCom_PyObjectFromIUnknown

    # noinspection PyTypeChecker
    com_obj.argtypes = (ctypes.POINTER(IUnknown),
                        ctypes.c_void_p,
                        BOOL)
    com_obj.restype = ctypes.py_object

    # noinspection PyProtectedMember
    return com_obj(ptr._comobj, byref(interface._iid_), True)


