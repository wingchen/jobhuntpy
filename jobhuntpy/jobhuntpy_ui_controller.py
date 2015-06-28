from Cocoa import *
from Foundation import NSObject


class UIController(NSWindowController):

    connectionsTableView = objc.IBOutlet()

    jobsTableView = objc.IBOutlet()

    exportConnectionsButton = objc.IBOutlet()

    exportJobsButton = objc.IBOutlet()

    exportAllJobsButton = objc.IBOutlet()

    keywordField = objc.IBOutlet()

    def windowDidLoad(self):
        NSWindowController.windowDidLoad(self)

    def getJobsByConnection(self, sender):
        pass

    @objc.IBAction
    def exportConnections(self, sender):
        pass

    @objc.IBAction
    def exportJobs(self, sender):
        pass

    @objc.IBAction
    def exportAllJobs(self, sender):
        pass