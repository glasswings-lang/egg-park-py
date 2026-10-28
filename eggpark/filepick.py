# SPDX-License-Identifier: CC0-1.0
"""The Windows file dialog, for choosing a recording from inside the game.

The ordinary Open dialog (IFileOpenDialog), so a screen reader already knows
every part of it, with one thing added: a Preview button, Alt+P, that plays
whatever is selected in the list. Choosing a sound by name alone means opening
each one somewhere else first; this way you can hear it before you pick it.

Built on comtypes, which is already here because accessible_output2 uses it.
The interfaces are declared by hand below, in vtable order. Only the methods
this file calls have their real signatures; the order of every method matters,
because a COM call goes by position in the table, not by name.
"""
import ctypes
import os
from ctypes import POINTER, byref, c_int, c_uint, c_void_p, c_wchar_p
from ctypes.wintypes import BOOL, DWORD, HWND, LPCWSTR, LPWSTR, UINT

import comtypes
import comtypes.client
from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

# Formats a recording can be in. Only the ones pyglet can decode on this
# machine are offered (see supported_extensions), so a file the game would
# fail to load never appears in the list.
AUDIO_EXTENSIONS = ('.wav', '.wave', '.mp3', '.flac', '.m4a', '.aac', '.wma')

TITLE = 'select the sound the game should play for this event'

PREVIEW_ID = 1

# The dialog remembers its last folder per client GUID: this one is Egg Park's,
# so choosing recordings here never moves where some other program's Open
# dialog starts, and vice versa.
_CLIENT_GUID = GUID('{6E1C5D1A-3F0B-4B8E-9C61-2A7E0B5D9F42}')

CLSID_FileOpenDialog = GUID('{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}')

FOS_NOCHANGEDIR = 0x8
FOS_FORCEFILESYSTEM = 0x40
FOS_PATHMUSTEXIST = 0x800
FOS_FILEMUSTEXIST = 0x1000

SIGDN_FILESYSPATH = 0x80058000
SFGAO_FOLDER = 0x20000000

ERROR_CANCELLED_HRESULT = -2147023673      # HRESULT_FROM_WIN32(ERROR_CANCELLED)


class COMDLG_FILTERSPEC(ctypes.Structure):
    _fields_ = [('pszName', LPCWSTR), ('pszSpec', LPCWSTR)]


class IShellItem(IUnknown):
    _iid_ = GUID('{43826D1E-E718-42EE-BC55-A1E261C37BFE}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'BindToHandler',
                  (['in'], c_void_p, 'pbc'), (['in'], POINTER(GUID), 'bhid'),
                  (['in'], POINTER(GUID), 'riid'), (['out'], POINTER(c_void_p), 'ppv')),
        COMMETHOD([], HRESULT, 'GetParent', (['out'], POINTER(POINTER(IUnknown)), 'ppsi')),
        # Strings the shell allocates come back as raw pointers, read and freed
        # by _text: left to comtypes, one came back as garbage characters.
        COMMETHOD([], HRESULT, 'GetDisplayName',
                  (['in'], c_uint, 'sigdnName'), (['out'], POINTER(c_void_p), 'ppszName')),
        COMMETHOD([], HRESULT, 'GetAttributes',
                  (['in'], c_uint, 'sfgaoMask'), (['out'], POINTER(c_uint), 'psfgaoAttribs')),
        COMMETHOD([], HRESULT, 'Compare',
                  (['in'], c_void_p, 'psi'), (['in'], DWORD, 'hint'),
                  (['out'], POINTER(c_int), 'piOrder')),
    ]


class IModalWindow(IUnknown):
    _iid_ = GUID('{B4DB1657-70D7-485E-8E3E-6FCB5A5C1802}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'Show', (['in'], HWND, 'hwndOwner')),
    ]


class IFileDialog(IModalWindow):
    _iid_ = GUID('{42F85136-DB7E-439C-85F1-E4075D135FC8}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'SetFileTypes',
                  (['in'], UINT, 'cFileTypes'), (['in'], POINTER(COMDLG_FILTERSPEC), 'rgFilterSpec')),
        COMMETHOD([], HRESULT, 'SetFileTypeIndex', (['in'], UINT, 'iFileType')),
        COMMETHOD([], HRESULT, 'GetFileTypeIndex', (['out'], POINTER(UINT), 'piFileType')),
        COMMETHOD([], HRESULT, 'Advise',
                  (['in'], POINTER(IUnknown), 'pfde'), (['out'], POINTER(DWORD), 'pdwCookie')),
        COMMETHOD([], HRESULT, 'Unadvise', (['in'], DWORD, 'dwCookie')),
        COMMETHOD([], HRESULT, 'SetOptions', (['in'], DWORD, 'fos')),
        COMMETHOD([], HRESULT, 'GetOptions', (['out'], POINTER(DWORD), 'pfos')),
        COMMETHOD([], HRESULT, 'SetDefaultFolder', (['in'], POINTER(IShellItem), 'psi')),
        COMMETHOD([], HRESULT, 'SetFolder', (['in'], POINTER(IShellItem), 'psi')),
        COMMETHOD([], HRESULT, 'GetFolder', (['out'], POINTER(POINTER(IShellItem)), 'ppsi')),
        COMMETHOD([], HRESULT, 'GetCurrentSelection', (['out'], POINTER(POINTER(IShellItem)), 'ppsi')),
        COMMETHOD([], HRESULT, 'SetFileName', (['in'], LPCWSTR, 'pszName')),
        COMMETHOD([], HRESULT, 'GetFileName', (['out'], POINTER(c_void_p), 'pszName')),
        COMMETHOD([], HRESULT, 'SetTitle', (['in'], LPCWSTR, 'pszTitle')),
        COMMETHOD([], HRESULT, 'SetOkButtonLabel', (['in'], LPCWSTR, 'pszText')),
        COMMETHOD([], HRESULT, 'SetFileNameLabel', (['in'], LPCWSTR, 'pszLabel')),
        COMMETHOD([], HRESULT, 'GetResult', (['out'], POINTER(POINTER(IShellItem)), 'ppsi')),
        COMMETHOD([], HRESULT, 'AddPlace', (['in'], POINTER(IShellItem), 'psi'), (['in'], c_int, 'fdap')),
        COMMETHOD([], HRESULT, 'SetDefaultExtension', (['in'], LPCWSTR, 'pszDefaultExtension')),
        COMMETHOD([], HRESULT, 'Close', (['in'], HRESULT, 'hr')),
        COMMETHOD([], HRESULT, 'SetClientGuid', (['in'], POINTER(GUID), 'guid')),
        COMMETHOD([], HRESULT, 'ClearClientData'),
        COMMETHOD([], HRESULT, 'SetFilter', (['in'], c_void_p, 'pFilter')),
    ]


class IFileOpenDialog(IFileDialog):
    _iid_ = GUID('{D57C7288-D4AD-4768-BE02-9D969532D960}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetResults', (['out'], POINTER(c_void_p), 'ppenum')),
        COMMETHOD([], HRESULT, 'GetSelectedItems', (['out'], POINTER(c_void_p), 'ppsai')),
    ]


class IFileDialogCustomize(IUnknown):
    _iid_ = GUID('{E6FDD21A-163F-4975-9C8C-A69F1BA37034}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'EnableOpenDropDown', (['in'], DWORD, 'dwIDCtl')),
        COMMETHOD([], HRESULT, 'AddMenu', (['in'], DWORD, 'dwIDCtl'), (['in'], LPCWSTR, 'pszLabel')),
        COMMETHOD([], HRESULT, 'AddPushButton', (['in'], DWORD, 'dwIDCtl'), (['in'], LPCWSTR, 'pszLabel')),
        COMMETHOD([], HRESULT, 'AddComboBox', (['in'], DWORD, 'dwIDCtl')),
        COMMETHOD([], HRESULT, 'AddRadioButtonList', (['in'], DWORD, 'dwIDCtl')),
        COMMETHOD([], HRESULT, 'AddCheckButton', (['in'], DWORD, 'dwIDCtl'),
                  (['in'], LPCWSTR, 'pszLabel'), (['in'], BOOL, 'bChecked')),
        COMMETHOD([], HRESULT, 'AddEditBox', (['in'], DWORD, 'dwIDCtl'), (['in'], LPCWSTR, 'pszText')),
        COMMETHOD([], HRESULT, 'AddSeparator', (['in'], DWORD, 'dwIDCtl')),
        COMMETHOD([], HRESULT, 'AddText', (['in'], DWORD, 'dwIDCtl'), (['in'], LPCWSTR, 'pszText')),
        # The rest are never called here, but they hold their places in the table.
        *[COMMETHOD([], HRESULT, name) for name in (
            'SetControlLabel', 'GetControlState', 'SetControlState', 'GetEditBoxText',
            'SetEditBoxText', 'GetCheckButtonState', 'SetCheckButtonState', 'AddControlItem',
            'RemoveControlItem', 'RemoveAllControlItems', 'GetControlItemState',
            'SetControlItemState', 'GetSelectedControlItem', 'SetSelectedControlItem',
            'StartVisualGroup', 'EndVisualGroup', 'MakeProminent', 'SetControlItemText')],
    ]


# The two event interfaces the dialog calls back on. One object implements
# both: the dialog is handed it by Advise and asks it for the second itself.
class IFileDialogEvents(IUnknown):
    _iid_ = GUID('{973510DB-7D7F-452B-8975-74A85828D354}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'OnFileOk', (['in'], c_void_p, 'pfd')),
        COMMETHOD([], HRESULT, 'OnFolderChanging', (['in'], c_void_p, 'pfd'), (['in'], c_void_p, 'psi')),
        COMMETHOD([], HRESULT, 'OnFolderChange', (['in'], c_void_p, 'pfd')),
        COMMETHOD([], HRESULT, 'OnSelectionChange', (['in'], c_void_p, 'pfd')),
        COMMETHOD([], HRESULT, 'OnShareViolation', (['in'], c_void_p, 'pfd'),
                  (['in'], c_void_p, 'psi'), (['in'], POINTER(c_int), 'pResponse')),
        COMMETHOD([], HRESULT, 'OnTypeChange', (['in'], c_void_p, 'pfd')),
        COMMETHOD([], HRESULT, 'OnOverwrite', (['in'], c_void_p, 'pfd'),
                  (['in'], c_void_p, 'psi'), (['in'], POINTER(c_int), 'pResponse')),
    ]


class IFileDialogControlEvents(IUnknown):
    _iid_ = GUID('{36116642-D713-4B97-9B83-7484A9D00433}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'OnItemSelected', (['in'], c_void_p, 'pfdc'),
                  (['in'], DWORD, 'dwIDCtl'), (['in'], DWORD, 'dwIDItem')),
        COMMETHOD([], HRESULT, 'OnButtonClicked', (['in'], c_void_p, 'pfdc'), (['in'], DWORD, 'dwIDCtl')),
        COMMETHOD([], HRESULT, 'OnCheckButtonToggled', (['in'], c_void_p, 'pfdc'),
                  (['in'], DWORD, 'dwIDCtl'), (['in'], BOOL, 'bChecked')),
        COMMETHOD([], HRESULT, 'OnControlActivating', (['in'], c_void_p, 'pfdc'), (['in'], DWORD, 'dwIDCtl')),
    ]


class _Events(comtypes.COMObject):
    """Says yes to everything the dialog asks, and plays on Preview."""

    _com_interfaces_ = [IFileDialogEvents, IFileDialogControlEvents]

    def __init__(self, dialog, on_preview):
        super().__init__()
        self._dialog = dialog
        self._on_preview = on_preview

    def OnButtonClicked(self, pfdc, dwIDCtl):
        if dwIDCtl == PREVIEW_ID:
            # A failure here must never escape into the dialog's own message
            # loop; whatever went wrong is passed on as "nothing to play".
            try:
                path = selected_path(self._dialog)
            except Exception:
                path = None
            self._on_preview(path)
        return 0

    # Every other event: carry on as normal.
    def OnFileOk(self, pfd): return 0
    def OnFolderChanging(self, pfd, psi): return 0
    def OnFolderChange(self, pfd): return 0
    def OnSelectionChange(self, pfd): return 0
    def OnShareViolation(self, pfd, psi, pResponse): return 0
    def OnTypeChange(self, pfd): return 0
    def OnOverwrite(self, pfd, psi, pResponse): return 0
    def OnItemSelected(self, pfdc, dwIDCtl, dwIDItem): return 0
    def OnCheckButtonToggled(self, pfdc, dwIDCtl, bChecked): return 0
    def OnControlActivating(self, pfdc, dwIDCtl): return 0


def supported_extensions():
    """The AUDIO_EXTENSIONS pyglet can decode here: WAV always, the rest only
    where Windows Media Foundation is there to decode them."""
    try:
        from pyglet.media.codecs import registry
        known = set()
        for decoder in registry.get_decoders():
            known.update(e.lower() for e in decoder.get_file_extensions())
    except Exception:
        known = {'.wav'}
    return [e for e in AUDIO_EXTENSIONS if e in known] or ['.wav']


def filter_spec():
    """(name, pattern) for the file-type box: the supported sounds, one entry."""
    patterns = ';'.join('*' + e for e in supported_extensions())
    names = ', '.join(e.lstrip('.').upper() for e in supported_extensions())
    return [(f'Sounds the game can play ({names})', patterns)]


def _text(raw):
    """A string the shell allocated, as str, its memory given back."""
    if not raw:
        return ''
    text = ctypes.wstring_at(raw)
    ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(raw))
    return text


def selected_path(dialog):
    """The file selected in the dialog right now, or None.

    The item selected in the list first. Failing that, a name typed into the
    File name box, taken against the folder the dialog is showing, so Preview
    plays what Open would open. None for nothing usable and for a folder:
    Preview on a folder has nothing to play, and saying so beats playing the
    last file again.
    """
    try:
        item = dialog.GetCurrentSelection()
    except comtypes.COMError:
        item = None
    if item:
        try:
            if item.GetAttributes(SFGAO_FOLDER) & SFGAO_FOLDER:
                return None
            path = _text(item.GetDisplayName(SIGDN_FILESYSPATH))
        except comtypes.COMError:
            path = ''
        return path if os.path.isfile(path) else None
    try:
        typed = _text(dialog.GetFileName()).strip().strip('"')
    except comtypes.COMError:
        return None
    if not typed:
        return None
    if not os.path.isabs(typed):
        try:
            typed = os.path.join(_text(dialog.GetFolder().GetDisplayName(SIGDN_FILESYSPATH)), typed)
        except comtypes.COMError:
            return None
    return typed if os.path.isfile(typed) else None


def _shell_item(path):
    shell32 = ctypes.windll.shell32
    fn = shell32.SHCreateItemFromParsingName
    fn.argtypes = [c_wchar_p, c_void_p, POINTER(GUID), POINTER(POINTER(IShellItem))]
    fn.restype = HRESULT
    item = POINTER(IShellItem)()
    fn(path, None, byref(IShellItem._iid_), byref(item))
    return item


def build(on_preview, start_in=None):
    """The configured dialog and its event sink, not yet shown.

    Separate from choose() so a test can build the real thing, and check
    every call made on it, without a window ever appearing.
    """
    dialog = comtypes.client.CreateObject(CLSID_FileOpenDialog, interface=IFileOpenDialog)
    specs = filter_spec()
    table = (COMDLG_FILTERSPEC * len(specs))(*[COMDLG_FILTERSPEC(n, p) for n, p in specs])
    dialog.SetFileTypes(len(specs), table)
    dialog.SetFileTypeIndex(1)
    dialog.SetTitle(TITLE)
    dialog.SetClientGuid(byref(_CLIENT_GUID))
    dialog.SetOptions(dialog.GetOptions() | FOS_FILEMUSTEXIST | FOS_PATHMUSTEXIST
                      | FOS_FORCEFILESYSTEM | FOS_NOCHANGEDIR)
    if start_in and os.path.isdir(start_in):
        try:
            dialog.SetFolder(_shell_item(start_in))
        except (comtypes.COMError, OSError):
            pass            # the remembered folder is a fine place to start
    customize = dialog.QueryInterface(IFileDialogCustomize)
    customize.AddPushButton(PREVIEW_ID, '&Preview')
    events = _Events(dialog, on_preview)
    cookie = dialog.Advise(events.QueryInterface(IUnknown))
    return dialog, events, cookie, table


def choose(owner_hwnd, on_preview, start_in=None):
    """Show the dialog; the chosen file's path, or None if it was cancelled.

    Modal to `owner_hwnd`: the game window waits until it closes. `on_preview`
    is called with the selected file's path, or None, each time Preview is
    pressed.
    """
    dialog, events, cookie, _table = build(on_preview, start_in)
    try:
        try:
            dialog.Show(owner_hwnd)
        except comtypes.COMError as exc:
            if exc.hresult == ERROR_CANCELLED_HRESULT:
                return None
            raise
        return _text(dialog.GetResult().GetDisplayName(SIGDN_FILESYSPATH))
    finally:
        try:
            dialog.Unadvise(cookie)
        except comtypes.COMError:
            pass
        del events
