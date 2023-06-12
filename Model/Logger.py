


class Logger:

    def __init__(self, bufferSize=1000) -> None:
        self.logs = []
        self.bufferSize = bufferSize
        self.currentLogIndex = 0
        self.logReactions = []

    def clearAllLogs(self):
        self.logs = []

    def clearOldLogs(self):
        self.logs = self.logs[self.currentLogIndex:]

    def writeToFile(self):
        pass 

    def getNewLogs(self):
        newLogs = self.logs[self.currentLogIndex:]
        self.currentLogIndex = len(self.logs) 
        return newLogs

    def getAllLogs(self):
        return self.logs

    def addNewLog(self, log):
        self.logs.append(log)
        self.logs = self.logs[len(self.logs) - self.bufferSize:]  
        [reaction() for reaction in self.logReactions]

    def reactToLogs(self, reaction):  
        self.logReactions.append(reaction)

        