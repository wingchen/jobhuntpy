import sys
import objc

from AppKit import *
from Cocoa import *
from Foundation import *
from PyObjCTools import AppHelper

app = None


class LoginController(NSWindowController):

    emailField = objc.IBOutlet()

    passwordField = objc.IBOutlet()

    messageLabel = objc.IBOutlet()

    loginButton = objc.IBOutlet()

    def windowDidLoad(self):
        NSWindowController.windowDidLoad(self)

    @objc.IBAction
    def login_(self, sender):
        # if not logged-in, show the error message in the label

        # if logged-in, disable the current window and bring in the real window
        print('here')
        uiController.showWindow_(uiController)


class UIMenuController(NSWindowController):

    @objc.IBAction
    def closeApplication_(self, sender):
        AppHelper.stopEventLoop()

    @objc.IBAction
    def exportConnections_(self, sender):
        pass

    @objc.IBAction
    def exportJobs_(self, sender):
        pass

    @objc.IBAction
    def exportAllJobs_(self, sender):
        pass


class MainUIController(NSWindowController):

    connectionsTableView = objc.IBOutlet()

    jobsTableView = objc.IBOutlet()

    exportConnectionsButton = objc.IBOutlet()

    exportJobsButton = objc.IBOutlet()

    exportAllJobsButton = objc.IBOutlet()

    keywordField = objc.IBOutlet()

    def getJobsByConnection(self, sender):
        pass


if __name__ == "__main__":
    app = NSApplication.sharedApplication()

    loginController = LoginController.alloc().initWithWindowNibName_("JobHuntLinkedinLoginUI")
    loginController.showWindow_(loginController)

    menuController = UIMenuController.alloc().initWithWindowNibName_("JobHuntPyUIMenu")
    menuController.showWindow_(menuController)

    uiController = MainUIController.alloc().initWithWindowNibName_("JobHuntPyUI")

    NSApp.activateIgnoringOtherApps_(True)

    AppHelper.runEventLoop()