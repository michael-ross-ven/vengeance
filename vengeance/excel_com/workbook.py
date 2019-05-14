
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

from .excel_constants import *
from ..util.filesystem import assert_path_exists
from ..util.filesystem import standardize_path
from ..util.text import vengeance_message

AccessibleObjectFromWindow = ctypes.oledll.oleacc.AccessibleObjectFromWindow
FindWindowEx               = ctypes.windll.user32.FindWindowExA

corrupt_hwnds = set()


def open_workbook(path, excel_instance=None,
                  *,
                  read_only=False,
                  update_links=True):

    wb = is_workbook_open(path)

    if wb is None:
        if not excel_instance:
            excel_app = empty_excel_instance() or new_excel_instance()
        else:
            excel_app = excel_instance

        wb = __workbook_from_excel_app(excel_app, path, update_links, read_only)

    elif excel_instance is not None:
        if wb.Application != excel_instance:
            vengeance_message("'{}' already open in another Excel instance".format(wb.Name))

    if wb.ReadOnly is False and read_only is True:
        vengeance_message("'{}' is NOT opened read-only".format(wb.Name))

    if wb.ReadOnly is True and read_only is False:
        vengeance_message("('{}' opened as read-only)".format(wb.Name))

    return wb


# noinspection PyUnusedLocal
def close_workbook(wb, save):
    """
    all references need to be severed for excel_com pointer to be released
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


def is_workbook_open(path):
    """ scan all open workbooks across all Excel sessions, match is determined by identical file path """
    path = standardize_path(path)
    assert_path_exists(path)

    window_h = FindWindowEx(0, 0, xl_class_name, None)
    while window_h != 0:
        for wb in __workbooks_from_hwnd(window_h):
            if standardize_path(wb.FullName) == path:
                return wb

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    return None


def new_excel_instance():
    excel_app = CreateObject('Excel.Application', dynamic=True)
    excel_app = __comtype_to_pywin_obj(excel_app, IDispatch)
    excel_app = pywin_dispatch(excel_app)

    excel_app.WindowState = xl_maximized
    excel_app.Visible = True

    app_to_foreground(excel_app)
    reload_all_add_ins(excel_app)

    return excel_app


def app_to_foreground(excel_app):
    SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow

    excel_app.Visible = True
    SetForegroundWindow(excel_app.Hwnd)


def reload_all_add_ins(excel_app):
    vengeance_message('reloading Excel add-ins...')

    for add_in in excel_app.AddIns:
        if add_in.Installed:
            name = add_in.Name
            try:
                add_in.Installed = False
                add_in.Installed = True
                vengeance_message('   {}'.format(name))
            except COMError:
                vengeance_message('failed to load add-in: {}' + name)
    print()


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
    return pywin_dispatch('Excel.Application')


def all_excel_instances():
    excel_apps = []
    window_h = FindWindowEx(0, 0, xl_class_name, None)

    while window_h != 0:
        excel_app = __excel_app_from_hwnd(window_h)
        if excel_app:
            excel_apps.append(excel_app)

        window_h = FindWindowEx(0, window_h, xl_class_name, None)

    return excel_apps


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
    """
    global corrupt_hwnds

    if window_h in corrupt_hwnds:
        return None

    desk_wnd   = FindWindowEx(window_h, None, xl_desk_class, None)
    excel7_wnd = FindWindowEx(desk_wnd, None, xl_excel7_class, None)

    if excel7_wnd == 0:
        corrupt_hwnds.add(window_h)
        # vengeance_message('(corrupt Excel application detected)')

        return None

    cls_id  = GUID.from_progid(xl_clsid)
    obj_ptr = POINTER(IDispatch)()
    AccessibleObjectFromWindow(excel7_wnd,
                               native_om,
                               byref(cls_id),
                               byref(obj_ptr))
    window = Dispatch(obj_ptr)

    try:
        com_ptr = window.Application
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

    com_obj.restype  = ctypes.py_object
    com_obj.argtypes = (ctypes.POINTER(IUnknown), ctypes.c_void_p, BOOL)

    # noinspection PyProtectedMember
    return com_obj(ptr._comobj, byref(interface._iid_), True)


