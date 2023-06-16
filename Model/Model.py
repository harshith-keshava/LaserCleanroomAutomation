
import glob
from ftplib import FTP
from time import sleep
import csv
import winsound
import os
from setuptools import Command
from ConfigFiles.MachineSettings import MachineSettings
from Model.BNRopcuaTag import BNRopcuaTag
from Model.LUTDataGeneration import LUTDataManager
from ConfigFiles.TestSettings import TestSettings
from opcua import Client
import numpy as np
from enum import Enum
import time
from datetime import datetime
import csv
from Model.Logger import Logger
import numpy as np
import statistics as stat
import pandas as pd
import plotly.express as px
from Model.FTP_Manager import FTP_Manager
import re
from apscheduler.schedulers.background import BackgroundScheduler

## ENUM to define the test modes 
## CONTINUOUS = user input only for pixels that are out of spec based on tolerance band or fail
## SEMI_AUTO = user input needed every pixel 
class TestMode(Enum):
        CONTINUOUS = 1
        SEMI_AUTO = 2

## Test Type Enum for the different types of tests that process team runs
## Calibration: Predefined tolerance band always run with Linear LUTS, run to generate new LUTs for the VFLCRs
## Clean Power Verification: Verification of laser health with generated LUTs with a clean debris shield
## Dirty Power Verification: Verification of laser health with generated LUTs with a dirty debris shield
## Low Power Check: Make sure the lasers are firing, basic test of function
class TestType(Enum):
        CALIBRATION = 0
        CLEAN_POWER_VERIFICATION = 1
        DIRTY_POWER_VERIFICATION = 2
        LOW_POWER_CHECK = 3

## Varaible that when changed calls a list of functions
## These functions can be added to variable in any amount
class SubscribedVariable:
    def __init__(self,value) -> None:
        self._value = value
        self.reactions = []

    @property
    def value(self):
        return self._value
       
    @value.setter
    def value(self, val):
        if self._value != val:
            self._value = val
            self.react()
    
    def react(self):
        [reaction() for reaction in self.reactions]

    def addReaction(self, reaction):
        self.reactions.append(reaction)
    
## Model tha defined the basis of the backend functionality and comminication with the PLC
class Model:

    def __init__(self, machineSettings, configurationSettings) -> None:
        self.testSettings = TestSettings() ## Current test settings given to the model through the user interface 
        self.laserTestData = [[] for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with power measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestEnergy = [[] for pixel in range(MachineSettings._numberOfPixels)] ##Data array that is populated during a test with energy measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestStatus = [5 for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with post test pixel status and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerData = [[] for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with commmanded Power Data(W) and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerLevels = [] ## Array generated with the power levels derived from processing commanded power data
        self.results = None ## Pandas Dataframe with cols: ["Date","Machine ID","Factory ID", "Test Type", "Pixel", "Process Acceptance", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation"]. Processed Results of a test
        self._lutDataManager = LUTDataManager(self.testSettings) ## Helper class to manage the LUT generation logic
        self._lutDataManager.changeTestSettings(self.testSettings) 
        self.logger = Logger() ## Logger to give information to the gui about the current test status
        self.saveLocation = "" ## Save path in the printer info drive of the processed data 
        self.periodicDataFile  = ""
        self.timeStamp = None ## New timestamp is created at the start of each test. Type = datetime.datetime.now()
        self.testInProgress = False
        self.currentPixelIndex = SubscribedVariable(0) ## Current pixel being test, reactions can be attached from view
        self.dataReady = SubscribedVariable(None) ## Returns true when processed data is ready, false when new test is started, reactions can be attached from view
        self.lutDataReady = SubscribedVariable(None) ## Returns true when lut data is ready after a calibration test, return false when any new test is started, reactions can be attached from view
        #Set initial test type and test mode
        self.TestType = TestType.CALIBRATION
        self.TestMode = TestMode.SEMI_AUTO
        self.dataCollector = BackgroundScheduler()
        self.testName = ""
    
        ############################################# ADD TAGS #########################################

        # Connection of the client using the freeopcua library
        if machineSettings._simulation:
            self.client = Client(f'''opc.tcp://127.0.0.1:{machineSettings._portNumber}''', timeout=5)
        else: 
            self.client = Client(f'''opc.tcp://{machineSettings._ipAddress}:{machineSettings._portNumber}''', timeout=5)

        # plcTags is a dictionary allowing the user to access the plc tags by string and perform a single action on all of them in a loop
        # new tags can be added without changing the model code
        self.plcTags = {"pulseDelayMsec": BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.pulseDelayMsec"),
        "pulseOnMsec": BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.pulseOnMsec"),
        "pulseOffMsec":BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.pulseOffMsec"),
        "numPulsesPerLevel":BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.numPulsesPerLevel"),
        "availableLaserPowerWatts":BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.availableLaserPowerWatts"),
        "safePowerLimitWatts":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.safePowerLimitWatts"),
        "startingPowerLevel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.startingPowerLevel"),
        "numPowerLevelSteps":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.numPowerLevelSteps"),
        "powerLevelIncrement":BNRopcuaTag(self.client,"ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.LaserParameters.powerLevelIncrement"),
        "PixelList":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.PixelList"),
        "NumPixelsToTest":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.NumPixelsToTest"),
        "TestPixel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.TestPixel"),
        "BeginTest":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.BeginTest"),
        "ErrorNum":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.ErrorNum"),
        "ConfigurationSent":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.ConfigurationSent"),
        "TestComplete":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.TestComplete"),
        "LaserPowerData":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.LaserPowerData"),
        "ActivePixel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ActivePixel"),
        "ProceedToNextPixel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.ProceedToNextPixel"),
        "ReadyToConfigure":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ReadyToConfigure"),
        "ReadyToTest":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ReadyToTest"),
        "TestStatus":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.TestStatus"),
        "CurrentPowerWatts":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.CurrentPowerWatts"),
        "UserAccessLevel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.UserAccessLevel"),
        "TestType": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.TestType"),
        "ScaledEnergyLive": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ScaledEnergyLive"),
        "PercentErrorLive": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.PercentErrorLive"),
        "AbortTest": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.AbortTest"),
        "MachineName": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.MachineName"),
        "ViablePixelList": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ViablePixelList"),
        "CurrentLUTID": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.CurrentLUTID"),
        "DeleteLUTs": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.DeleteLUTs"),
        "UploadLUTs": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.UploadLUTs"),
        "ToleranceBandPercent": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.ToleranceBandPercent"),
        "FactoryName": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.FactoryName"),
        "ExpectedValueCoefficient" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromCalibApp.ExpectedValueCoefficient"),
        "ConfigValid" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ConfigValid"),
        "BuildLotID" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.BuildLotID"),
        "OpticsBoxFlow": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxFlow"),
        "ChillerOutputTemp": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ChillerOutputTemp"),
        "ChillerReturnTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.ChillerReturnTemp"),
        "OpticsBoxFiberHolderTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxFiberHolderTemp"),
        "OpticsBoxMiMaSinkTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxMiMaSinkTemp"),
        "OpticsBoxBeamBlockATemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxBeamBlockATemp"),
        "OpticsBoxBeamBlockBTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxBeamBlockBTemp"),
        "OpticsBoxBeamBlockCTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxBeamBlockCTemp"),
        "OpticsBoxSinkUpperTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxSinkUpperTemp"),
        "OpticsBoxSinkMiddleTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxSinkMiddleTemp"),
        "OpticsBoxSinkLowerTemp" : BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.OpticsBoxSinkLowerTemp"),
        # gen3 stuff below here
        "HeartbeatOut":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.HeartbeatOut"),
        "HeartbeatIn":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.HeartbeatIn"),
        "ExampleCommand": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ExampleCommand"),
        "ExampleResult": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ExampleResult"),
        "InitializePixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.InitializePixel"),
        "PixelInitialized": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelInitialized"),
        "CapturePixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CapturePixel"),
        "PixelCaptured": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelCaptured"),
        "ProcessPixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ProcessPixel"),
        "PixelProcessed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelProcessed"),
        "PixelResult": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelResult")}

        # definition of all the plc tags as a variable bound to the dictionary element
        # this is redundant to the dictionary but give the option to use dot operators to access the tags rather than strings
        # this makes tags come up in the autocomplete of the test editor vs having the remember/lookup the exact string
        # new tags do not have to be added here in addition to the dictionary but they can be 
        self.pulseDelayMsecTag = self.plcTags["pulseDelayMsec"]
        self.pulseOnMsecTag = self.plcTags["pulseOnMsec"]
        self.pulseOffMsecTag = self.plcTags["pulseOffMsec"]
        self.numPulsesPerLevelTag = self.plcTags["numPulsesPerLevel"]
        self.availableLaserPowerWattsTag = self.plcTags["availableLaserPowerWatts"]
        self.safePowerLimitWattsTag = self.plcTags["safePowerLimitWatts"]
        self.startingPowerLevelTag = self.plcTags["startingPowerLevel"]
        self.numPowerLevelStepsTag = self.plcTags["numPowerLevelSteps"]
        self.powerLevelIncrementTag = self.plcTags["powerLevelIncrement"]
        self.testPixelsTag = self.plcTags["PixelList"]
        self.testPixelsToTestTag = self.plcTags["NumPixelsToTest"]
        self.testPixelTag = self.plcTags["TestPixel"]
        self.beginTestTag = self.plcTags["BeginTest"]
        self.configurationSentTag = self.plcTags["ConfigurationSent"]
        self.testCompleteTag = self.plcTags["TestComplete"]
        self.laserPowerDataTag = self.plcTags["LaserPowerData"]
        self.activePixelTag = self.plcTags["ActivePixel"] 
        self.proceedToNextPixelTag = self.plcTags["ProceedToNextPixel"]
        self.currentPowerWattsTag= self.plcTags["CurrentPowerWatts"]
        self.PixelListTag = self.plcTags["PixelList"]
        self.TestTypeTag = self.plcTags["TestType"]
        self.ScaledEnergyLiveTag = self.plcTags["ScaledEnergyLive"]
        self.PercentErrorLiveTag = self.plcTags["PercentErrorLive"]
        self.viablePixelListTag = self.plcTags["ViablePixelList"]
        self.MachineNameTag = self.plcTags["MachineName"]
        self.AbortTestTag = self.plcTags["AbortTest"]
        self.DeleteLUTsTag = self.plcTags["DeleteLUTs"]
        self.UploadLUTsTag = self.plcTags["UploadLUTs"]
        self.ToleranceBandPercentTag = self.plcTags["ToleranceBandPercent"]
        self.FactoryNameTag = self.plcTags["FactoryName"]
        self.ExpectedValueCoefficient = self.plcTags["ExpectedValueCoefficient"]
        self.ConfigValid = self.plcTags["ConfigValid"]

        self.heartBeatIntag = self.plcTags["HeartbeatIn"]        
        self.exampleResultTag = self.plcTags["ExampleResult"]
        self.pixelInitializedTag = self.plcTags["PixelInitialized"]
        self.pixelCapturedTag = self.plcTags["PixelCaptured"]
        self.pixelProcessedTag = self.plcTags["PixelProcessed"]
        self.pixelResultTag = self.plcTags["PixelResult"]

        ### Subscribed Variables (must also add these to the delete)
        ###     -> Variables that update using a callback based on the status of the tag on the plc 
        self.readyToConfigureTag = self.plcTags["ReadyToConfigure"]
        self.readyToTestTag = self.plcTags["ReadyToTest"]
        self.errorNumTag = self.plcTags["ErrorNum"]
        self.testStatusTag = self.plcTags["TestStatus"]
        self.userAccessLevelTag = self.plcTags["UserAccessLevel"]
        self.CurrentLUTIDTag = self.plcTags["CurrentLUTID"]

        self.heartBeatOutTag = self.plcTags["HeartbeatOut"]
        self.exampleCommandTag = self.plcTags["ExampleCommand"]
        self.initializePixelTag = self.plcTags["InitializePixel"]
        self.capturePixelTag = self.plcTags["CapturePixel"]
        self.processPixelTag = self.plcTags["ProcessPixel"]

        ### Lookup Tables for Data Outputs #####
        self.testStatusTable = ["In Progress", "Passed", "High Power Failure", "Low Power Failure", "No Power Failure", "Untested", "", "", "", "", "Abort"]
        self.testTypesAsString = ["None", "LOWPOWER", "CAL", "CVER", "DVER"]
        self.errorCodes = ["", "PIXEL OUT OF BOUNDS", "DISABLED PIXEL", "ZERO FIRST ELEMENT", "ZERO TEST PIXEL", "ZERO NUM PULSES", "ZERO AVAILABLE POWER", "ZERO SAFE LIMIT", "ZERO STARTING POWER"]

    ############################################ GENERAL TEST FUNCTIONS ######################################################
   
    ## Creates the connection to the PLC and connections to the subscribed variables to their respective plc tags
    ## New subscribed variables can be set as updating here 
    def connectToPlc(self):
        try:
            self.client.connect()  
            self.logger.addNewLog("Connections made")
            self.readyToConfigureTag._setAsUpdating()
            self.readyToTestTag._setAsUpdating()
            self.testStatusTag._setAsUpdating()
            self.errorNumTag._setAsUpdating()
            self.proceedToNextPixelTag._setAsUpdating()
            self.userAccessLevelTag._setAsUpdating()
            self.CurrentLUTIDTag._setAsUpdating()
            self.ConfigValid._setAsUpdating()
            self.testStatusTag.attachReaction(self.testStatusReaction)

            # monitor for change
            self.exampleCommandTag._setAsUpdating()
            self.heartBeatOutTag._setAsUpdating()
            self.initializePixelTag._setAsUpdating()
            self.capturePixelTag._setAsUpdating()
            self.processPixelTag._setAsUpdating()

            # attach reaction on change
            self.exampleCommandTag.attachReaction(self.exampleCommandReaction)
            self.heartBeatOutTag.attachReaction(self.heartBeatReaction)
            self.initializePixelTag.attachReaction(self.initializePixelReaction)
            self.capturePixelTag.attachReaction(self.capturePixelReaction)
            self.processPixelTag.attachReaction(self.processPixelReaction)

            if self.FactoryNameTag.value == "VulcanOne":
                MachineSettings._factoryID = "V1"
            else:
                MachineSettings._factoryID = self.FactoryNameTag.value
            MachineSettings._machineID = self.MachineNameTag.value
            self.dataCollector.start(paused=True)
        except:
            print("Could not connect to server")
            self.logger.addNewLog("Could not connect to server, check the connection to the PLC")
    
    ## Called on application close
    ## New to disconnect the connected opcua tags or the program crashes, issue with the freeopcua library
    def disconnect(self):
        [self.plcTags[key]._removeUpdates() for key in self.plcTags]
        self.logger.addNewLog("Disconnecting")
        self.client.disconnect()

    ## Send the laser test parameters to the plc, required parameters for testing. There are defaults for each of the test
    def sendConfigSettings(self):
        self.logger.addNewLog("Sending Configuration.....")
        self.PixelListTag.setPlcValue(list(np.zeros(84)))
        self.pulseDelayMsecTag.setPlcValue(self.testSettings._pulseDelayMsec)
        self.pulseOnMsecTag.setPlcValue(self.testSettings._pulseOnMsec)
        self.pulseOffMsecTag.setPlcValue(self.testSettings._pulseOffMsec)
        self.numPowerLevelStepsTag.setPlcValue(self.testSettings._numPowerLevelSteps)
        self.availableLaserPowerWattsTag.setPlcValue(self.testSettings._availableLaserPowerWatts)
        self.startingPowerLevelTag.setPlcValue(self.testSettings._startingPowerLevel)
        self.powerLevelIncrementTag.setPlcValue(self.testSettings._powerLevelIncrement)
        self.safePowerLimitWattsTag.setPlcValue(self.testSettings._safePowerLimitWatts)
        self.numPulsesPerLevelTag.setPlcValue(self.testSettings._numPulsesPerLevel)
        self.TestTypeTag.setPlcValue(self.testSettings._testType)
        self.ToleranceBandPercentTag.setPlcValue(self.testSettings._tolerancePercent)
        self.PixelListTag.setPlcValue(list(self.testSettings._pixelList))
        self.testPixelTag.setPlcValue(int(self.testSettings._pixelList[0]))
        self.logger.addNewLog(str(self.testSettings.settingsAsDict()))
        sleep(0.25)
        self.configurationSentTag.setPlcValue(True)
        self.logger.addNewLog("Configuration Sent")
        if self.errorNumTag.value > 0:
            self.logger.addNewLog("Configuration Error:" + self.errorCodes[self.errorNumTag.value])

    ## Function called from the view that tells the model to begin the test 
    ## Resets all the data arrays to fill for the test and tells the plc to start the start
    def startTest(self): 
        self.logger.addNewLog("Starting test")
        self.testInProgress = True
        self.timeStamp = datetime.utcnow()
        
        if MachineSettings._simulation:
            self.saveLocation = ".\\tmp\\output"
        else:
            self.saveLocation = self._createoutputdirectory()
            os.makedirs(self.saveLocation)

        self.periodicDataFile  = self.saveLocation + "\\opticsBoxData.csv"
        self.writePeriodicDataHeaders()
        self.createLogFile()
        self.currentPixelIndex.value = 0
        self.results = None
        self.laserTestData = [[] for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with power measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestEnergy = [[] for pixel in range(MachineSettings._numberOfPixels)] ##Data array that is populated during a test with energy measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestStatus = [5 for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with post test pixel status and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerData = [[] for pixel in range(MachineSettings._numberOfPixels)] ## Data array that is populated during a test with commmanded Power Data(W) and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerLevels = [] ## Array generated with the power levels derived from processing commanded power data
        self.dataReady.value = False
        self.lutDataReady.value = False
        self.beginTestTag.setPlcValue(True)
        self.testCompleteTag.setPlcValue(False)
        self.dataCollector.add_job(self.logPeriodicData, 'interval', seconds=30)
        self.dataCollector.resume()
    
    ## Tells the plc what the new pixel is to test and tells the plc to test the pixel in the sequence
    def goToNextPixel(self):
        if(self.testStatusTag.value != 4):
            self.currentPixelIndex.value += 1
        else:
            self.currentPixelIndex.value += 2
        if(self.currentPixelIndex.value < len(self.testSettings._pixelList)):
            self.logger.addNewLog("Going to next pixel.....")
            self.logger.addNewLog("Current Pixel is now " + str(self.currentPixelIndex.value))
            self.testPixelTag.setPlcValue(self.testSettings._pixelList[self.currentPixelIndex.value])
            stopwatchStart = time.time()
            while(self.activePixelTag.value != self.testSettings._pixelList[self.currentPixelIndex.value]):
                if(time.time() - stopwatchStart > 3):
                    self.endTest()
            self.proceedToNextPixelTag.setPlcValue(True)
        else:
            self.endTest()
       

    ## Takes care of creating the log file, also goes to printer info drive to give tester info about the test
    def createLogFile(self):
        with open('tmp\\log.csv', 'w', newline='') as csvfile:
            logFileWriter = csv.writer(csvfile, delimiter=',')
            date_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            logFileWriter.writerow(["Date", date_time])
            logFileWriter.writerow(["Operator", self.testSettings._operatorName])
            logFileWriter.writerow(["Sensor Number", self.testSettings._sensorNumber])
            logFileWriter.writerow(["Juno+ Serial", self.testSettings._junoPlusSerial])
            settings = self.testSettings.settingsAsDict()
            for setting in settings:
                logFileWriter.writerow([setting, str(settings[setting])])
        with open(self.saveLocation + "\\log.csv", 'w', newline='') as csvfile:
            logFileWriter = csv.writer(csvfile, delimiter=',')
            date_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            logFileWriter.writerow(["Date", date_time])
            logFileWriter.writerow(["Operator", self.testSettings._operatorName])
            logFileWriter.writerow(["Sensor Number", self.testSettings._sensorNumber])
            logFileWriter.writerow(["Juno+ Serial", self.testSettings._junoPlusSerial])
            settings = self.testSettings.settingsAsDict()
            for setting in settings:
                logFileWriter.writerow([setting, str(settings[setting])])
   
    ## Called at the end of the test. Calls the functions to post-process the data and the save the end of test files
    def endTest(self):
        self.dataCollector.remove_all_jobs()
        self.dataCollector.pause()
        self.testInProgress = False
        self.logger.addNewLog("Test Ended")
        self.testCompleteTag.setPlcValue(True)
        self.laserTestData = list([np.trim_zeros(np.array(pixelData)) for pixelData in self.laserTestData])
        self.commandedPowerData = list([np.trim_zeros(np.array(pixelData)) for pixelData in self.commandedPowerData])
        self.commandedPowerLevels = [(self.testSettings._startingPowerLevel + self.testSettings._powerLevelIncrement * powerLevel) * 525/255 for powerLevel in range(self.testSettings._numPowerLevelSteps)]
        self.exportData()
        self.testPixelTag.setPlcValue(0)
        self.generateTestResultDataFrame()
        if self.testSettings._testType == 2:
            self.generateLuts()

    ## Sends the abort signal to the PLC and saves out whatever data is currently captured in the data arrays 
    def abortTest(self):
        self.dataCollector.remove_all_jobs()
        self.dataCollector.pause()
        self.AbortTestTag.setPlcValue(True)
        self.logger.addNewLog("Test Aborted")
        self.laserTestStatus = [10 if idx > self.currentPixelIndex.value else status for idx, status in enumerate(self.laserTestStatus)]
        if(len(self.laserTestData) > 0 and self.testInProgress):
            print("Writing abort data")
            self.laserTestData = list([np.trim_zeros(np.array(pixelData)) for pixelData in self.laserTestData])
            self.commandedPowerLevels = [(self.testSettings._startingPowerLevel + self.testSettings._powerLevelIncrement * powerLevel) * 525/255 for powerLevel in range(self.testSettings._numPowerLevelSteps)]
            self.exportData()
        if len(self.laserTestData) > 0 and self.testInProgress:
            self.generateTestResultDataFrame()
        self.testInProgress = False

    ## Called by the end of test and abort sequences
    ## Saves the data into a project temporary folder
    def exportData(self):
        self.logger.addNewLog("Exporting data.......")
        exportData = self.laserTestData.copy()
        fullRankVal = max([len(pixelData) for pixelData in exportData])
        exportData = [np.pad(np.array(pixelData), (0, fullRankVal - len(pixelData))) for pixelData in exportData]
        with open('tmp\LPM_raw.csv', 'w', newline='') as csvfile:
            rawOutputWriter = csv.writer(csvfile, delimiter=',')
            for pixelIdx, pixelTested in enumerate(exportData):
                rawOutputWriter.writerow([pixelIdx + 1] + [self.laserTestStatus[pixelIdx]] + list(pixelTested))
        
        with open(self.saveLocation + '\\LPM_Raw.csv', 'w', newline='') as csvfile:
            rawOutputWriter = csv.writer(csvfile, delimiter=',')
            for pixelIdx, pixelTested in enumerate(exportData):
                rawOutputWriter.writerow([pixelIdx + 1] + [self.laserTestStatus[pixelIdx]] + list(pixelTested))
        self.logger.addNewLog("Raw data saved to the tmp folder and " + self.saveLocation)

    ## Creating the dataframe for the process team and the database team
    ## Dataframe headers are ["DateTime","Factory", "Machine", "TestType","Pixel","Rack", "Laser","Status","Commanded Power","Pulse Power Average","Pulse Power Stdv","Pulse Power Deviation"]
    ## saves to local temporary folder which is rewritten every test and the printerinfo drive     
    def generateTestResultDataFrame(self):
        self.logger.addNewLog("Created processed data from raw test data......")
        commandedPowerLevels = [(self.testSettings._startingPowerLevel + self.testSettings._powerLevelIncrement * powerLevel) * 525/255 for powerLevel in range(self.testSettings._numPowerLevelSteps)]
        pulseSplitData = []
        for pixelIdx, pixelrawdata in enumerate(self.laserTestData):
            if len(pixelrawdata) == 0:
                pulseSplitData.append([])
            else:
                pulseChangeIndexes = [pwrIdx + 1 for pwrIdx, powerDiff in enumerate(np.diff(self.commandedPowerData[pixelIdx])) if powerDiff > 0]
                pulseChangeIndexes.insert(0,0)
                pulseChangeIndexes.append(len(pixelrawdata) + 1)
                pulseSplitData.append([pixelrawdata[pulseChangeIndexes[idx]:pulseChangeIndexes[idx+1]] for idx in range(len(pulseChangeIndexes)-1)])
        avg_daq_p_data = np.array([[stat.mean(pixelData[levelNum]) if (levelNum < len(pixelData) and len(pixelData[levelNum]) > 0)  else np.NaN for levelNum in range(len(commandedPowerLevels))] for pixelData in pulseSplitData]).round(decimals=3)
        std_daq_p_data = np.array([[stat.stdev(pixelData[levelNum]) if (levelNum < len(pixelData) and len(pixelData[levelNum]) > 1) else np.NaN for levelNum in range(len(commandedPowerLevels))] for pixelData in pulseSplitData]).round(decimals=3)
        dev_daq_p_data = np.array([[self.percentDiff(pulseAvgData, commandedPowerLevels[pulseNum]) if (not np.isnan(pulseAvgData)) else np.NaN for pulseNum, pulseAvgData in enumerate(pixelData)] for pixelData in avg_daq_p_data]).round(decimals=3)
        outputData = []
        for pixelIdx, data in enumerate(self.laserTestData):         
            for powerLevelNum, powerLevelData in enumerate(avg_daq_p_data[pixelIdx]):
                #["DateTime","Factory", "Machine", "TestType","Pixel","Rack", "Laser","Status","Commanded Power","Pulse Power Average","Pulse Power Stdv","Pulse Power Deviation"]
                if self.laserTestStatus[pixelIdx] != 5:
                    commandedPower = round(commandedPowerLevels[powerLevelNum], 2)
                else:
                    commandedPower = np.nan
                if len(pulseSplitData[pixelIdx]) > powerLevelNum:
                    numDataPoints = len(pulseSplitData[pixelIdx][powerLevelNum])
                else:
                    numDataPoints = 0
                outputData.append([self.timeStamp.strftime("%Y-%m-%d,%H:%M:%S"), MachineSettings._machineID, MachineSettings._factoryID, self.testTypesAsString[self.testSettings._testType], pixelIdx + 1, MachineSettings._vfpMap[pixelIdx][2], MachineSettings._vfpMap[pixelIdx][3],dev_daq_p_data[pixelIdx][powerLevelNum] < 5, self.testStatusTable[self.laserTestStatus[pixelIdx]], commandedPower, avg_daq_p_data[pixelIdx][powerLevelNum], std_daq_p_data[pixelIdx][powerLevelNum], dev_daq_p_data[pixelIdx][powerLevelNum], numDataPoints])
        cols =["Date","Machine ID","Factory ID", "Test Type", "Pixel", "Rack", "Laser", "Process Acceptance", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation", "Data Points"] # add rack and laser printer name, name of test(CVER, DVER....), timestamp  
        self.results = pd.DataFrame(outputData, columns=cols)
        self.results.to_csv("tmp\\LPM_processed.csv", index=False)
        self.results.to_csv(self.saveLocation + "\\LPM_processed.csv", index=False)
        self.dataReady.value = True
        validRanges = ["ValidRanges"]
        validRanges.append(self.getValidPixelRanges())
        with open(self.saveLocation + '\\summary.csv', 'w',newline='') as summaryFile:
            writer = csv.writer(summaryFile)
            writer.writerows(self.getSummary())
            writer.writerow(validRanges)
        return self.results

    def getSummary(self):
        summary = self.results.groupby("Commanded Power",as_index=False)[['Pulse Power Average', "Pulse Power Stdv", "Pulse Power Deviation"]].mean()
        summary = np.round_(summary.to_numpy(), decimals=3).astype('str')
        summary = np.insert(summary,0,['Commanded Power', 'Total Power Average', 'Total Average Power Stdv', 'Total Average Power Deviation'], axis=0).tolist()
        return summary
    
    def getValidPixelRanges(self):
        passedPixels = self.results.loc[self.results["Status"] == "Passed"]["Pixel"].to_numpy()
        validRanges = []
        startRange = 1
        for pixel in range(1,MachineSettings._numberOfPixels+1):
            if pixel not in passedPixels and startRange is not None:
                validRanges.append([startRange, pixel-1])
                startRange = None
            elif startRange is None and pixel in passedPixels:
                startRange = pixel
        return validRanges


    def generateLuts(self):
        luts = self._lutDataManager.convertLaserDataToLUTData(self.laserTestData, self.commandedPowerData, self.laserTestStatus, self.testSettings._CalId, saveLocation=self.saveLocation)
        bins = self._lutDataManager.convertLUTDataToBinaries(luts)
        self.lutDataReady.value = True

    def uploadLinearLuts(self):
        self.DeleteLUTsTag.setPlcValue(True)
        lutExistsStatus = [True for VFLCR in MachineSettings._vflcrIPs]
        while(any(lutExistsStatus)):
            for vflcrNum, vflcrIP in enumerate(MachineSettings._vflcrIPs):
                lutExistsStatus[vflcrNum] = not FTP_Manager.lutsEmpty(vflcrIP)
        self._lutDataManager.uploadLinearLuts()
        self.UploadLUTsTag.setPlcValue(True)

    def uploadCalibratedLuts(self, calibrationID:int):
        self.logger.addNewLog("Writing binaries to folders and printer.......")
        self.DeleteLUTsTag.setPlcValue(True)
        binpath = self.saveLocation + "\\bin\\"
        self._lutDataManager.writeBinariesToFolder(calibrationID, binPath=binpath)
        lutExistsStatus = [True for VFLCR in MachineSettings._vflcrIPs]
        while(any(lutExistsStatus)):
            for vflcrNum, vflcrIP in enumerate(MachineSettings._vflcrIPs):
                lutExistsStatus[vflcrNum] = not FTP_Manager.lutsEmpty(vflcrIP)
        if not os.path.exists(binpath):
            os.makedirs(binpath)
        self.logger.addNewLog("Binaries written to folder complete")
        self._lutDataManager.writeBinaryArraysToVFPLCs(calibrationID)
        self.logger.addNewLog("Binaries written to printer complete")
        self.UploadLUTsTag.setPlcValue(True)

    def uploadPreviousLuts(self, calibrationID:int):
        self.DeleteLUTsTag.setPlcValue(True)
        lutExistsStatus = [True for VFLCR in MachineSettings._vflcrIPs]
        while(any(lutExistsStatus)):
            for vflcrNum, vflcrIP in enumerate(MachineSettings._vflcrIPs):
                lutExistsStatus[vflcrNum] = not FTP_Manager.lutsEmpty(vflcrIP)
        machineID = str(MachineSettings._machineID)[0:2] + str(MachineSettings._machineID[2:]).zfill(2)
        calibrations = os.listdir('\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "30_Calibrations")
        for calibration in calibrations:
            if(int(str(calibration).split('_')[2]) == calibrationID):
                previousLUTPath = '\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "30_Calibrations\\" + calibration
                break
        bins = os.listdir(previousLUTPath)
        for bin in bins:
            FTP_Manager.writeBinaryFileToVfplc(MachineSettings._vflcrIPs[int(str(bin).split('\\')[-1].split('_')[1][1:]) - 1], str(bin).split('\\')[-1])
          
    def writePeriodicDataHeaders(self):
        with open(self.periodicDataFile, 'w') as dataFile:
            dataFile.write("OpticsBoxFlow(GPM),ChillerOutputTemp(C),ChillerReturnTemp(C),OpticsBoxFiberHolderTemp(C),OpticsBoxMiMaSinkTemp(C),OpticsBoxBeamBlockATemp(C),OpticsBoxBeamBlockBTemp(C),OpticsBoxBeamBlockCTemp(C),OpticsBoxSinkUpperTemp(C),OpticsBoxSinkMiddleTemp(C),OpticsBoxSinkLowerTemp(C)\n")

    def logPeriodicData(self):
        self.logger.addNewLog("logging optics box data")
        opticsBoxData = np.array([self.plcTags["OpticsBoxFlow"].value,
        self.plcTags["ChillerOutputTemp"].value,
        self.plcTags["ChillerReturnTemp"].value,
        self.plcTags["OpticsBoxFiberHolderTemp"].value,
        self.plcTags["OpticsBoxMiMaSinkTemp"].value,
        self.plcTags["OpticsBoxBeamBlockATemp"].value,
        self.plcTags["OpticsBoxBeamBlockBTemp"].value,
        self.plcTags["OpticsBoxBeamBlockCTemp"].value,
        self.plcTags["OpticsBoxSinkUpperTemp"].value,
        self.plcTags["OpticsBoxSinkMiddleTemp"].value,
        self.plcTags["OpticsBoxSinkLowerTemp"].value])
        with open(self.periodicDataFile, 'ab') as dataFile:
            opticsBoxData.tofile(dataFile, sep=',')
            dataFile.write(b'\n')

    def disablePixel(self, pixel):
        pixel, enable, rack, laser = MachineSettings._vfpMap[pixel - 1]
        pixelEnableTag = BNRopcuaTag(self.client, 'ns=6;s=::AsGlobalPV:gCommissioningSettings.laserControlSystem.rackConfig[{rack}].ignoreLaser[{laser}]'.format(rack=int(rack), laser=int(laser)))
        pixelEnableTag.setPlcValue(True)
        print(pixelEnableTag.value)
        return

    ## STILL NEEDS TO BE IMPLEMENTED
    def uploadLUTsFromFolder(self, filepath):
        files = glob.glob(filepath + "\\*.vflpc")
        lutNumber = int(re.split('-|_|.', files[0])[5][2:])
        #self._lutDataManager.writeBinaryArraysToVFPLCs(lutNumber, )

    ## Example Command
    def exampleCommand(self):
        self.exampleResultTag.setPlcValue(1)

    def initializePixel(self):
        self.pixelInitializedTag.setPlcValue(1)

    def capturePixel(self):
        self.pixelCapturedTag.setPlcValue(1)

    def processPixel(self):
        self.pixelResultTag.setPlcValue(1)  # autopass
        self.pixelProcessedTag.setPlcValue(1)
    
    ## Use this one function for a bunch of response resets if possible
    def resetResponseTags(self):
        self.exampleResultTag.setPlcValue(0)
        self.pixelResultTag.setPlcValue(0)
        self.pixelInitializedTag.setPlcValue(0)
        self.pixelCapturedTag.setPlcValue(0)     
        self.pixelProcessedTag.setPlcValue(0)


    ##################################### TAG REACTIONS ###################################################################
    def testStatusReaction(self):
        testStatus = self.testStatusTag.value
        self.logger.addNewLog("Test status Changed to " + str(testStatus))
        if testStatus == 0:
            pass
        elif testStatus == 1:
            self.logger.addNewLog("tested pixel " + str(self.currentPixelIndex.value + 1) + " out of " + str(len(self.testSettings._pixelList)) + " passed")
            self._collectTestData(testStatus)
            if self.TestMode == TestMode.CONTINUOUS:
                self.goToNextPixel()
        
        elif testStatus == 2 or testStatus == 3:
            winsound.MessageBeep(-1)
            self.logger.addNewLog("tested pixel " + str(self.currentPixelIndex.value + 1) + " out of " + str(len(self.testSettings._pixelList)) + " failed")
            self._collectTestData(testStatus)

        elif testStatus == 4:
            winsound.MessageBeep(-1)
            self.logger.addNewLog("tested pixel " + str(self.currentPixelIndex.value + 1) + " out of " + str(len(self.testSettings._pixelList)) + " failed, no power")
            self._collectTestData(testStatus)
        elif testStatus == 10:
            self.logger.addNewLog("Critical test failure, aborting....")
            self.abortTest()

    def heartBeatReaction(self):
        self.heartBeatIntag.setPlcValue(self.heartBeatOutTag.value + 1)

    def exampleCommandReaction(self):
        cmd = self.exampleCommandTag.value
        if cmd == True:
            self.logger.addNewLog("Example command sent by PLC ")
            self.exampleCommand()
        if cmd == False:
            self.resetResponseTags()

    def initializePixelReaction(self):
        cmd = self.initializePixelTag.value
        if cmd == True:
            self.logger.addNewLog("Initialize pixel command received from PLC ")
            self.initializePixel()
        if cmd == False:
            self.resetResponseTags()
        
    def capturePixelReaction(self):
        cmd = self.capturePixelTag.value
        if cmd == True:
            self.logger.addNewLog("Capture pixel command received from  PLC ")
            self.capturePixel()
        if cmd == False:
            self.resetResponseTags()

    def processPixelReaction(self):
        cmd = self.processPixelTag.value
        if cmd == True:
            self.logger.addNewLog("Process pixel command received from  PLC ")
            self.processPixel()
        if cmd == False:
            self.resetResponseTags()

############################################# ADDING REACTIONS ##############################################

    def addRecurringReaction(self, reaction):
            pass

    def addTagReaction(self, tag, reaction):
        self.plcTags[tag].attachReaction(reaction)
        
    def addTag(self, opcuaTagString, updating=False, reaction=None):
        self.plcTags[opcuaTagString] = BNRopcuaTag(self.client, BNRopcuaTag)
        if updating:
            self.plcTags[opcuaTagString]._setAsUpdating()
        if reaction is not None:
            self.addTagReaction(opcuaTagString, reaction)

    def OnPixelChange(self, reaction):
        self.currentPixelIndex.addReaction(reaction)

    def OnDataReady(self, reaction):
        self.dataReady.addReaction(reaction)

    def OnLUTDataReady(self, reaction):
        self.lutDataReady.addReaction(reaction)

    def addLogReactions(self, reaction):
        self.logger.reactToLogs(reaction)

    ###################################### Getter/Setter functions ##############################
    def getCurrentLaserPower(self):
        commandedPowerWatts = self.currentPowerWattsTag.value
        return commandedPowerWatts

    def getErrorCode(self):
        return self.errorNumTag.value

    def getLaserPowerData(self):
        return list(np.asarray(self.laserPowerDataTag.value)/(float(self.testSettings._pulseOnMsec)/1000))
        
    def getResults(self):
        return self.results
    
    def getError(self):
        return self.errorCodes[self.errorNumTag.value]

    def getLUTResults(self):
        return self._lutDataManager.results_lut

    def getTestStatus(self):
        return self.testStatusTag.value

    def getViablePixelList(self):
        return list(np.trim_zeros(np.array(self.viablePixelListTag.value)))

    def isReadyToTest(self):
        return self.readyToTestTag.value & self.readyToConfigureTag.value

    def isTestComplete(self):
        return self.testCompleteTag.value

    def getCurrentPixelIndex(self):
        return self.currentPixelIndex.value

    def getCalibrationId(self):
        return self.CurrentLUTIDTag.value

    def updateTestSettings(self, testSettings:TestSettings):
        self.testSettings = testSettings
        self._lutDataManager.changeTestSettings(testSettings)

    def changeTestMode(self, testMode):
        if testMode == 0:
            self.TestMode = TestMode.SEMI_AUTO
        elif testMode == 1:
            self.TestMode = TestMode.CONTINUOUS
        self.logger.addNewLog(str(self.TestMode))

    def isConfigValid(self):
        return self.ConfigValid.value

   ############################## HELPER FUNCTION ##########################################

    def _collectTestData(self, testStatus):
        laserData = self.laserPowerDataTag.value
        self.laserTestData[self.activePixelTag.value - 1] = list(np.array(laserData)/(self.testSettings._pulseOnMsec / 1000))
        self.laserTestEnergy[self.activePixelTag.value - 1] = laserData
        self.laserTestStatus[self.activePixelTag.value - 1] =testStatus
        self.commandedPowerData[self.activePixelTag.value - 1] = self.currentPowerWattsTag.value
       
    def _createoutputdirectory(self):
        date = self.timeStamp.strftime("%Y%m%d")
        machineID = str(MachineSettings._machineID)[0:2] + str(MachineSettings._machineID[2:]).zfill(2)
        if(self.testSettings._testType == 1):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(r'\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_LOWPOWER")
            self.testName = machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_LOWPOWER"
        elif(self.testSettings._testType == 2):    
            calID = self.testSettings._CalId  
            drivePath = os.path.join(r'\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "30_Calibrations", machineID + "_LUT_" + str(calID).zfill(5)+"_" + date)
            self.testName = machineID + "_LUT_" + str(calID).zfill(5)+"_" + date + " Calibration"
        elif(self.testSettings._testType == 3):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(r'\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_CVER")
            self.testName = machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_CVER"
        elif(self.testSettings._testType == 4):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(r'\\brl-nas02',"printerinfo", MachineSettings._factoryID, machineID,"Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_DVER")
            self.testName = machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_DVER"
        
        counter = 1
        while(os.path.exists(drivePath)):
            if drivePath[-3] == '_':
                drivePath = drivePath[:-3]
            drivePath = drivePath + '_' + str(counter).zfill(2)
            counter += 1
        return drivePath

    @staticmethod
    def percentDiff(numA, numB):
        if numA == numB:
            return 0
        try:
            return (abs(numA - numB) / numB) * 100.0
        except ZeroDivisionError:
            return float('inf')

