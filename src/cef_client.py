import logging
from cefpython3 import cefpython as cef
import platform
import sys
import ctypes
import json
import time

logger = logging.getLogger(__name__)

def get_npsso_token(auth_params, psnplugin):
    time.sleep(2)
    
    sys.excepthook = cef.ExceptHook  # To shutdown all CEF processes on error
    
    settings = {
        "debug": False,
        "log_severity": cef.LOGSEVERITY_ERROR,
        "log_file": "",
        "remote_debugging_port": -1,
    }
    cef.Initialize(settings)
    browser = cef.CreateBrowserSync(url=auth_params['start_uri'], window_title=auth_params['window_title'])
    #visitor need to init outside of handler or it will be destoyed before call
    frame_source_visitor = FrameSourceVisitor()
    frame_source_visitor.npsso_token = ""
    frame_source_visitor.browser = browser
    load_handler = LoadHandler()
    load_handler.oauth_login_redirect_url = auth_params['end_uri']
    load_handler.frame_source_visitor = frame_source_visitor
    load_handler.is_loaded = False
    browser.SetClientHandler(load_handler)
    browser.SetFocus(True)
    
    if platform.system() == "Windows":
        window_handle = browser.GetOuterWindowHandle()
        insert_after_handle = 0
        # X and Y parameters are ignored by setting the SWP_NOMOVE flag
        SWP_NOMOVE = 0x0002
        # noinspection PyUnresolvedReferences
        ctypes.windll.user32.SetWindowPos(window_handle, insert_after_handle, 0, 0, auth_params['window_width'], auth_params['window_height'], SWP_NOMOVE)
        
        wnd = browser.GetWindowHandle()
        ForegroundThreadID = ctypes.windll.user32.GetWindowThreadProcessId(ctypes.windll.user32.GetForegroundWindow(), None)
        ThisThreadID = ctypes.windll.user32.GetWindowThreadProcessId(wnd, None)
        if ctypes.windll.user32.AttachThreadInput(ThisThreadID, ForegroundThreadID, True):
            ctypes.windll.user32.BringWindowToTop(wnd)
            ctypes.windll.user32.SetForegroundWindow(wnd)
            ctypes.windll.user32.AttachThreadInput(ThisThreadID, ForegroundThreadID, False)
    
    cef.MessageLoop()
    del browser
    cef.Shutdown()
    
    #logger.debug("npsso_token: %s", frame_source_visitor.npsso_token)
    npsso = ""
    try:
        data = json.loads(frame_source_visitor.npsso_token)
        npsso = data['npsso']
    except:
        npsso = ""
    finally:
        psnplugin._npsso_token = npsso

class LoadHandler(object):
    def OnLoadEnd(self, browser, frame, http_code, **_):
        # OnLoadEnd should be called only once
        if self.is_loaded:
            return
        url = browser.GetUrl()
        if url == self.oauth_login_redirect_url:
            logger.debug("LoadHandler got end_uri")
            self.is_loaded = True
            frame.GetText(self.frame_source_visitor)

class FrameSourceVisitor(object):
    def Visit(self, value):
        logger.debug("FrameSourceVisitor set token")
        self.npsso_token = value
        self.browser.CloseBrowser(True)
