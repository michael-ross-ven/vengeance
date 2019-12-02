
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

# from win32com.client import Dispatch as pywin_dispatch                      # late-bound reference
from win32com.client.gencache import EnsureDispatch as pywin_dispatch       # early-bound reference

from .excel_constants import xlMaximized
from ..util.filesystem import assert_path_exists
from ..util.filesystem import standardize_path
from ..util.text import vengeance_message

FindWindowEx = ctypes.windll.user32.FindWindowExA
AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow

corrupt_hwnds = set()

# ascii-encoding important for compatability wtih C++ safearray strings in FindWindowExA
xl_class_name   = 'XLMAIN'.encode('ascii')
xl_desk_class   = 'XLDESK'.encode('ascii')
xl_excel7_class = 'EXCEL7'.encode('ascii')

xl_clsid  = '{00020400-0000-0000-C000-000000000046}'
native_om = -16


def open_workbook(path,
                  excel_app=None,
                  *,
                  read_only=False,
                  update_links=True):

    wb = is_workbook_open(path)

    if wb is None:
        if excel_app in (None, 'new'):
            excel_app = new_excel_instance()
        elif excel_app == 'empty':
            excel_app = empty_excel_instance()
        elif excel_app == 'any':
            excel_app = any_excel_instance()

        wb = __open_workbook(excel_app, path, update_links, read_only)

    if (wb.ReadOnly is False) and read_only:
        raise AssertionError("'{}' is not opened read-only".format(wb.Name))

    if wb.ReadOnly and (read_only is False):
        vengeance_message("('{}' opened as read-only)".format(wb.Name))

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
    provides a few conveniences that the client may not want to deal with
        1) if Workbook is the only one in the Excel application, closes the application as well
        2) correctly releases the com pointer for the workbook
    """
    if save and wb.ReadOnly:
        raise AssertionError("'{}' is open as read-only, cannot save and close".format(wb.Name))

    excel_app = wb.Application
    display_alerts = excel_app.DisplayAlerts

    if save:
        wb.Save()

    excel_app.DisplayAlerts = False

    wb.Close()
    wb = None

    if excel_app.Workbooks.Count == 0:
        excel_app.Quit()
        excel_app = None
    else:
        excel_app.DisplayAlerts = display_alerts


def new_excel_instance():
    excel_app = CreateObject('Excel.Application', dynamic=True)     # comtypes method
    excel_app = __comtype_to_pywin_obj(excel_app, IDispatch)
    excel_app = pywin_dispatch(excel_app)

    excel_app.WindowState = xlMaximized

    excel_app_to_foreground(excel_app)
    reload_all_add_ins(excel_app)

    return excel_app


def empty_excel_instance():
    window_h = FindWindowEx(0, 0, xl_class_name, None)

    while window_h != 0:
        excel_app = __excel_app_from_hwnd(window_h)

        if __is_excel_app_empty(excel_app):
            vengeance_message('utilizing empty Excel instance')
            return excel_app

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    raise AssertionError('empty Excel instance not found')


def any_excel_instance():
    excel_app = pywin_dispatch('Excel.Application')
    if not excel_app:
        excel_app = new_excel_instance()

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


def excel_app_to_foreground(excel_app):
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


def __open_workbook(excel_app, path, update_links, read_only):
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
    comtypes library is used to search windows handles for Excel application,
    then converts the application pointer to a pywin object

    xl_clsid
        found in HKEY_CLASSES_ROOT

    # noinspection PyTypeChecker
    obj_ptr = POINTER(IDispatch)()
        IDispatch is expected type Type[_CT] ?
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
    cls_id  = GUID.from_progid(xl_clsid)
    AccessibleObjectFromWindow(excel7_wnd,
                               native_om,
                               byref(cls_id),
                               byref(obj_ptr))

    try:
        com_ptr   = Dispatch(obj_ptr).Application
        excel_app = __comtype_to_pywin_obj(com_ptr, IDispatch)
    except (COMError, com_error, NameError) as e:
        raise ChildProcessError('remote procedure call to Excel application rejected\n\n'
                                '(check if cursor is still active within a cell somewhere, '
                                'Excel will reject automation calls while waiting on '
                                'user input)') from e
    try:
        excel_app = pywin_dispatch(excel_app)
        excel_app.Visible = True

        return excel_app

    except AttributeError as e:
        raise AttributeError('Error loading win32com module: \n\n'
                             'deleting the gencache folder then re-running function may resolve the issue \n'
                             'gencache folder: %userprofile%\\AppData\\Local\\Temp\\gen_py') from e


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


