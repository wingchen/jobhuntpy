import sys

from Cocoa import *
from Foundation import NSObject


class LoginController(NSWindowController):

    emailField = objc.IBOutlet()

    passwordField = objc.IBOutlet()

    messageLabel = objc.IBOutlet()

    loginButton = objc.IBOutlet()

    def windowDidLoad(self):
        NSWindowController.windowDidLoad(self)

    def windowShouldClose_(self, sender):
        print "Should Close?"
        return 0

    @objc.IBAction
    def logIntoLinkedin_(self, sender):
        # if not logged-in, show the error message in the label
        # if logged-in, disable the current window and bring in the real window
        print('log in...')


if __name__ == "__main__":
    app = NSApplication.sharedApplication()

    # Initiate the controller with a XIB
    viewController = LoginController.alloc().initWithWindowNibName_("JobHuntLinkedinLoginUI")

    # Show the window
    viewController.showWindow_(viewController)

    # Bring app to top
    NSApp.activateIgnoringOtherApps_(True)

    from PyObjCTools import AppHelper
    AppHelper.runEventLoop()