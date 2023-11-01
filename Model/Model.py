import os
import csv
import time
import numpy as np
import statistics as stat
import pandas as pd
from enum import Enum
from datetime import datetime
from minio import Minio
from minio.error import S3Error
import urllib3
import urllib3.exceptions
from opcua import Client
from ConfigFiles.MachineSettings import MachineSettings
from Model.BNRopcuaTag import BNRopcuaTag
from Model.LUTDataGeneration import LUTDataManager
from ConfigFiles.TestSettings import TestSettings
from Model.Logger import Logger
from Model.FTP_Manager import FTP_Manager
from Model.CameraDriver import CameraDriver
from Model.OphirCom import OphirJunoCOM
from Model.LaserSettings import LaserSettings
from Model.metadatawriter import MetadataFileWriter
import zaber.serial
import wx
import wx.lib.activex

import logging
logger = logging.getLogger('model')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh = logging.FileHandler(filename='camera_driver.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)
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
        SOMS_TEST = 4

## Default tolerance percentages for each test type
testTolerancePercents = {
        TestType.CALIBRATION: 30,
        TestType.CLEAN_POWER_VERIFICATION: 5,
        TestType.DIRTY_POWER_VERIFICATION: 5,
        TestType.LOW_POWER_CHECK: 10
    }

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

    def __init__(self, machineSettings, configurationSettings: TestSettings, laserSettings: LaserSettings) -> None:
        self.laserSettings = laserSettings    # object that holds pixel map, number of pixels info
        self.testSettings = configurationSettings ## Current test settings given to the model through the user interface 
        self.laserTestData = [[] for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with power measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestEnergy = [[] for pixel in range(self.laserSettings.numberOfPixels)] ##Data array that is populated during a test with energy measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestStatus = [5 for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with post test pixel status and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerData = [[] for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with commmanded Power Data(W) and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerLevels = [] ## Array generated with the power levels derived from processing commanded power data
        self.results = None ## Pandas Dataframe with cols: ["Date", "Machine ID", "Factory ID", "Test Type", "Pixel", "Process Acceptance", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation"]. Processed Results of a test
        self._lutDataManager = LUTDataManager(self.testSettings) ## Helper class to manage the LUT generation logic
        self.logger = Logger() ## Logger to give information to the gui about the current test status
        self.saveLocation = os.path.join(".", "tmp") ## Save path in the printer info drive of the processed data 
        self.resultsLocation = os.path.join(".", "tmp") ## Results path in the printer info drive of the processed results from MLDS app 
        self.timeStamp = None ## New timestamp is created at the start of each test. Type = datetime.datetime.now()
        #Set initial test type and test mode
        self.TestType = TestType.CALIBRATION
        self.camera = CameraDriver()
        self.pyrometer = OphirJunoCOM()
        self.pyrometer.connectToJuno()
        print("Juno connection:" + str(self.pyrometer.isConnected))
        self.testName = ""
        self.currentPowerLevelIndex = 0 ## power level counter to adjust camera exposure
        self.exposureAt100W = 1 ## 1ms exposure at 100W pulse
        self.http = urllib3.PoolManager()
        self.metadatafilewriter = None

        # Camera init
        self.app = wx.App()
        self.frame = wx.Frame( parent=None, id=wx.ID_ANY,size=(900,900), 
                              title='Python Interface to DataRay')
        p = wx.Panel(self.frame,wx.ID_ANY) # TODO: is this actually necessary?
        # Get Data
        self.gd = wx.lib.activex.ActiveXCtrl(p, 'DATARAYOCX.GetDataCtrl.1')
        # Set some parameters to avoid potential AttributeErrors on failed connection
        self.softwareVersion = ''
        self.cameraNID = 0

        self._PyroMultiplicationFactor = 1.73

        # Software Version - vMajor.Minor.Patch eg: v1.2.0
        self.applicationMajorVersion = 0
        self.applicationMinorVersion = 2
        self.applicationPatchVersion = 0
        ############################################# ADD TAGS #########################################

        # Connection of the client using the freeopcua library
        if machineSettings._simulation:
            self.client = Client(f'''opc.tcp://127.0.0.1:{machineSettings._portNumber}''', timeout=5)
        else: 
            self.client = Client(f'''opc.tcp://{machineSettings._ipAddress}:{machineSettings._portNumber}''', timeout=5)

        # plcTags is a dictionary allowing the user to access the plc tags by string and perform a single action on all of them in a loop
        # new tags can be added without changing the model code
        self.plcTags = {

        # App version
        "AppMajorVersion":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.AppMajorVersion"),
        "AppMinorVersion":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.AppMinorVersion"),
        "AppPatchVersion":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.AppPatchVersion"),

        # machine info
        "MachineName": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.MachineName"),
        "FactoryName": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.FactoryName"),

        # heartbeat
        "HeartbeatOut":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.HeartbeatOut"),
        "HeartbeatIn":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.HeartbeatIn"),
        
        # example
        "ExampleCommand": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ExampleCommand"),
        "ExampleResult": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ExampleResult"),
        
        # initialize calibration
        "InitializeCalibration": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.InitializeCalibration"),
        "CalibrationInitialized": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.CalibrationInitialized"),
        
        # initialize pixel
        "InitializePixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.InitializePixel"),
        "PixelInitialized": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelInitialized"),
        
        # capture pixel
        "CapturePixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CapturePixel"),
        "CaptureFrame": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CaptureFrame"),
        "CaptureFrameInstance": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CaptureFrameInstance"),
        "FrameCaptureInstanceResponse": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.FrameCaptureInstanceResponse"),
        "PixelCaptured": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelCaptured"),
        "pulseOnMsec": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.LaserParameters.pulseOnTime_ms"),
        "numPulsesPerLevel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.LaserParameters.numPulsesPerLevel"),
        "startingPowerLevel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.LaserParameters.startingPowerLevel"),
        "numPowerLevelSteps":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.LaserParameters.numPowerLevels"),
        "powerLevelIncrement":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.LaserParameters.powerIncrementPerStep"),
        "CurrentPowerWatts":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CurrentPowerWatts"),

        # process pixel
        "ProcessPixel": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ProcessPixel"),
        "PixelProcessed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelProcessed"),
        "PixelResult": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.PixelResult"),
        
        # process calibration
        "ProcessCalibration": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ProcessCalibration"),
        "CalibrationProcessed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.CalibrationProcessed"),

        # pixel iteration
        "ActivePixel":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ActivePixel"),
        "VFPMap":BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.VFPMap"),

        # Test Type
        "TestType": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.TestType"),

        # LUTs
        "UploadLinearLUTs": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.UploadLinearLUTs"),
        "UploadCalibratedLUTs": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.UploadCalibratedLUTs"),
        "LUTsUploaded": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.LUTsUploaded"),
        "CurrentLUTID": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CurrentLUTID"),

        # Process test data
        "UploadTestData": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.UploadTestData"),
        "TestDataUploaded": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.TestDataUploaded"),
        "DownloadTestResults": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.DownloadTestResults"),
        "TestResultsDownloaded": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.TestResultsDownloaded"),
        "ParseTestResults": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ParseTestResults"),
        "TestResultsParsed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.TestResultsParsed"),

        # Error responses
        "ErrorBucketNotExist": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ErrorBucketNotExist"),
        "ErrorS3Connection": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ErrorS3Connection"),
        "ErrorCaptureFailed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ErrorCaptureFailed"),
        "ErrorFrameCaptureFailed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ErrorFrameCaptureFailed"),

        # Pixel data sent back to PLC
        "MeasuredPower": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.MeasuredPower"),
        "CommandedPower": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.CommandedPower"),
        "LaserTestStatus": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.LaserTestStatus"),

        # Zaber data
        "ZaberPosition": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ZaberPosition"),
        "ZaberHomed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.ZaberHomed"),

        "ZaberRelativePosPar": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberRelativePos_mm"),
        "ZaberAbsolutePosPar": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberAbsolutePos_mm"),
        "ZaberHome": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberHome"),
        "ZaberMoveRelative": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberMoveRelative"),
        "ZaberMoveAbsolute": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberMoveAbsolute"),
        "ZaberGetHomeStatus": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberGetHomeStatus"),
        "ZaberGetPosFeedback": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.ZaberGetPosFeedback"),

        # Additional Meta Data
        "GantryXPositionStatus": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.GantryXPositionStatus"),
        "GantryYPositionStatus": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.GantryYPositionStatus"),

        #OMS 
        "StartOMSTest": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.StartOMSTest"),
        "MetaDataWriterReady": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.MetaDataWriterReady"),
        "TestCompleteProcessed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.TestCompleteProcessed"),
        "TestAbortProcessed": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_FromGen3CalibApp.TestAbortProcessed"),
        "OMSTestComplete": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.OMSTestComplete"),
        "OMSTestAborted": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.OMSTestAborted"),
        "CameraExposure": BNRopcuaTag(self.client, "ns=6;s=::AsGlobalPV:gOpcData_ToGen3CalibApp.CameraExposure")

        }

        # definition of all the plc tags as a variable bound to the dictionary element
        # this is redundant to the dictionary but give the option to use dot operators to access the tags rather than strings
        # this makes tags come up in the autocomplete of the test editor vs having the remember/lookup the exact string
        # new tags do not have to be added here in addition to the dictionary but they can be 

        self.AppMajorVersionTag = self.plcTags["AppMajorVersion"]
        self.AppMinorVersionTag = self.plcTags["AppMinorVersion"]
        self.AppPatchVersionTag = self.plcTags["AppPatchVersion"]

        self.MachineNameTag = self.plcTags["MachineName"]
        self.FactoryNameTag = self.plcTags["FactoryName"]

        self.heartBeatIntag = self.plcTags["HeartbeatIn"]        
        
        self.exampleResultTag = self.plcTags["ExampleResult"]
        
        self.calibrationInitializedTag = self.plcTags["CalibrationInitialized"]

        self.pixelInitializedTag = self.plcTags["PixelInitialized"]
        
        self.pixelCapturedTag = self.plcTags["PixelCaptured"]
        self.pulseOnMsecTag = self.plcTags["pulseOnMsec"]
        self.numPulsesPerLevelTag = self.plcTags["numPulsesPerLevel"]
        self.startingPowerLevelTag = self.plcTags["startingPowerLevel"]
        self.numPowerLevelStepsTag = self.plcTags["numPowerLevelSteps"]
        self.powerLevelIncrementTag = self.plcTags["powerLevelIncrement"]
        self.currentPowerWattsTag= self.plcTags["CurrentPowerWatts"]


        self.pixelProcessedTag = self.plcTags["PixelProcessed"]
        self.pixelResultTag = self.plcTags["PixelResult"]

        self.calibrationProcessedTag = self.plcTags["CalibrationProcessed"]

        self.activePixelTag = self.plcTags["ActivePixel"]  # 1-indexed pixel that is currently being used
        self.vfpMapTag = self.plcTags["VFPMap"] 

        self.TestTypeTag = self.plcTags["TestType"]

        self.UploadLinearLUTsTag = self.plcTags["UploadLinearLUTs"]
        self.UploadCalibratedLUTsTag = self.plcTags["UploadCalibratedLUTs"]
        self.LUTsUploadedTag = self.plcTags["LUTsUploaded"]
        
        self.testDataUploadedTag = self.plcTags["TestDataUploaded"]
        self.testResultsDownloadedTag = self.plcTags["TestResultsDownloaded"]
        self.testResultsParsedTag = self.plcTags["TestResultsParsed"]
        
        self.errorBucketNotExistTag = self.plcTags["ErrorBucketNotExist"]
        self.errorS3ConnectionTag = self.plcTags["ErrorS3Connection"]
        self.errorCaptureFailedTag = self.plcTags["ErrorCaptureFailed"]
        self.errorFrameCaptureFailedTag = self.plcTags["ErrorFrameCaptureFailed"]
        

        ### Subscribed Variables (must also add these to the delete)
        ###     -> Variables that update using a callback based on the status of the tag on the plc 
        self.CurrentLUTIDTag = self.plcTags["CurrentLUTID"]
        self.heartBeatOutTag = self.plcTags["HeartbeatOut"]
        self.exampleCommandTag = self.plcTags["ExampleCommand"]
        self.initializeCalibrationTag = self.plcTags["InitializeCalibration"]
        self.initializePixelTag = self.plcTags["InitializePixel"]
        self.capturePixelTag = self.plcTags["CapturePixel"]
        self.captureFrameTag = self.plcTags["CaptureFrame"]
        self.CaptureFrameInstanceTag = self.plcTags["CaptureFrameInstance"]
        self.FrameCaptureInstanceResponseTag = self.plcTags["FrameCaptureInstanceResponse"]
        self.processPixelTag = self.plcTags["ProcessPixel"]
        self.processCalibrationTag = self.plcTags["ProcessCalibration"]
        self.uploadTestDataTag = self.plcTags["UploadTestData"]
        self.downloadTestResultsTag = self.plcTags["DownloadTestResults"]
        self.parseTestResultsTag = self.plcTags["ParseTestResults"]
        self.MeasuredPowerTag = self.plcTags["MeasuredPower"]
        self.CommandedPowerTag = self.plcTags["CommandedPower"]
        self.LaserTestStatusTag = self.plcTags["LaserTestStatus"]

        self.ZaberPositionTag = self.plcTags["ZaberPosition"]
        self.ZaberHomedTag = self.plcTags["ZaberHomed"]

        self.ZaberRelativePosParTag = self.plcTags["ZaberRelativePosPar"]
        self.ZaberAbsolutePosParTag = self.plcTags["ZaberAbsolutePosPar"]
        self.ZaberHomeTag = self.plcTags["ZaberHome"]
        self.ZaberMoveRelativeTag = self.plcTags["ZaberMoveRelative"]
        self.ZaberMoveAbsoluteTag = self.plcTags["ZaberMoveAbsolute"]
        self.ZaberGetHomeStatusTag = self.plcTags["ZaberGetHomeStatus"]
        self.ZaberGetPosFeedbackTag = self.plcTags["ZaberGetPosFeedback"]

        self.GantryXPositionStatusTag = self.plcTags["GantryXPositionStatus"]
        self.GantryYPositionStatusTag = self.plcTags["GantryYPositionStatus"]

        self.StartOMSTestTag = self.plcTags["StartOMSTest"]
        self.MetaDataWriterReadyTag = self.plcTags["MetaDataWriterReady"]
        self.TestCompleteProcessedTag = self.plcTags["TestCompleteProcessed"]
        self.TestAbortProcessedTag = self.plcTags["TestAbortProcessed"]
        self.OMSTestCompleteTag = self.plcTags["OMSTestComplete"]
        self.OMSTestAbortedTag = self.plcTags["OMSTestAborted"]
        self.CameraExposureTag = self.plcTags["CameraExposure"]
    
        ### Lookup Tables for Data Outputs #####
        self.testStatusTable = ["In Progress", "Passed", "High Power Failure", "Low Power Failure", "No Power Failure", "Untested", "", "", "", "", "Abort"]
        self.testTypesAsString = ["None", "LOWPOWER", "CAL", "CVER", "DVER"]

        self._last_captured_frame = None
    ############################################ GENERAL TEST FUNCTIONS ######################################################
   
    ## Creates the connection to the PLC and connections to the subscribed variables to their respective plc tags
    ## New subscribed variables can be set as updating here 
    def connectToPlc(self):
        try:
            self.client.connect()
            self.AppMajorVersionTag.setPlcValue(self.applicationMajorVersion)
            self.AppMinorVersionTag.setPlcValue(self.applicationMinorVersion)
            self.AppPatchVersionTag.setPlcValue(self.applicationPatchVersion) 

        except:
            print("Could not connect to server")
            self.logger.addNewLog("Could not connect to server, check the connection to the PLC")
        
        try:
            self.logger.addNewLog("Connections made")

            # monitor for change
            #self.exampleCommandTag._setAsUpdating()
            self.heartBeatOutTag._setAsUpdating()
            self.initializeCalibrationTag._setAsUpdating()
            self.initializePixelTag._setAsUpdating()
            self.capturePixelTag._setAsUpdating()
            self.captureFrameTag._setAsUpdating()
            self.CaptureFrameInstanceTag._setAsUpdating()
            self.processPixelTag._setAsUpdating()
            self.processCalibrationTag._setAsUpdating()
            self.UploadLinearLUTsTag._setAsUpdating()
            self.UploadCalibratedLUTsTag._setAsUpdating()
            self.uploadTestDataTag._setAsUpdating()
            self.downloadTestResultsTag._setAsUpdating()
            self.parseTestResultsTag._setAsUpdating()
            self.ZaberRelativePosParTag._setAsUpdating()
            self.ZaberAbsolutePosParTag._setAsUpdating()
            self.ZaberHomeTag._setAsUpdating()
            self.ZaberMoveRelativeTag._setAsUpdating()
            self.ZaberMoveAbsoluteTag._setAsUpdating()
            self.ZaberGetHomeStatusTag._setAsUpdating()
            self.ZaberGetPosFeedbackTag._setAsUpdating()
            self.GantryXPositionStatusTag._setAsUpdating()
            self.GantryYPositionStatusTag._setAsUpdating()
            self.StartOMSTestTag._setAsUpdating()
            self.OMSTestCompleteTag._setAsUpdating()
            self.OMSTestAbortedTag._setAsUpdating()
        except:
            print("OPCUA subscription setup failed")

        try:
            # attach reaction on change
            self.exampleCommandTag.attachReaction(self.exampleCommandReaction)
            self.heartBeatOutTag.attachReaction(self.heartBeatReaction)
            self.initializeCalibrationTag.attachReaction(self.initializeCalibrationReaction)
            self.initializePixelTag.attachReaction(self.initializePixelReaction)
            self.capturePixelTag.attachReaction(self.capturePixelReaction)
            self.captureFrameTag.attachReaction(self.captureFrameReaction)
            self.processPixelTag.attachReaction(self.processPixelReaction)
            self.processCalibrationTag.attachReaction(self.processCalibrationReaction)
            self.UploadLinearLUTsTag.attachReaction(self.uploadLinearLUTsReaction)
            self.UploadCalibratedLUTsTag.attachReaction(self.uploadCalibratedLUTsReaction)
            self.uploadTestDataTag.attachReaction(self.uploadTestDataReaction)
            self.downloadTestResultsTag.attachReaction(self.downloadTestResultsReaction)
            self.parseTestResultsTag.attachReaction(self.parseTestResultsReaction)
            self.ZaberHomeTag.attachReaction(self.ZaberHomeReaction)
            self.ZaberMoveRelativeTag.attachReaction(self.ZaberMoveRelativeReaction)
            self.ZaberMoveAbsoluteTag.attachReaction(self.ZaberMoveAbsoluteReaction)
            self.ZaberGetHomeStatusTag.attachReaction(self.ZaberGetHomeStatusReaction)
            self.ZaberGetPosFeedbackTag.attachReaction(self.ZaberGetPosFeedbackReaction)
            self.OMSTestCompleteTag.attachReaction(self.OMSTestCompleteReaction)
            self.OMSTestAbortedTag.attachReaction(self.OMSTestAbortedReaction)

        except:
            print("OPCUA reaction setup failed")

        if self.FactoryNameTag.value == "VulcanOne":
            MachineSettings._factoryID = "V1"
        else:
            MachineSettings._factoryID = self.FactoryNameTag.value
        MachineSettings._machineID = self.MachineNameTag.value

    ## Takes care of creating the log file, also goes to printer info drive to give tester info about the test
    def createLogFile(self):
        with open(os.path.join('tmp', 'log.csv'), 'w', newline='') as csvfile:
            logFileWriter = csv.writer(csvfile, delimiter=',')
            date_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            logFileWriter.writerow(["Date", date_time])
            logFileWriter.writerow(["Operator", self.testSettings._operatorName])
            logFileWriter.writerow(["Sensor Number", self.testSettings._sensorNumber])
            logFileWriter.writerow(["Juno+ Serial", self.testSettings._junoPlusSerial])
            settings = self.testSettings.settingsAsDict()
            for setting in settings:
                logFileWriter.writerow([setting, str(settings[setting])])
        with open(os.path.join(self.saveLocation, "log.csv"), 'w', newline='') as csvfile:
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
        self.logger.addNewLog("Test Ended")
        self.laserTestData = list([np.trim_zeros(np.array(pixelData)) for pixelData in self.laserTestData])
        self.commandedPowerData = list([np.trim_zeros(np.array(pixelData)) for pixelData in self.commandedPowerData])
        self.commandedPowerLevels = [(self.testSettings._startingPowerLevel + self.testSettings._powerLevelIncrement * powerLevel) * 525/255 for powerLevel in range(self.testSettings._numPowerLevelSteps)]
        self.exportData()
        self.generateTestResultDataFrame()
        if self.testType == TestType.CALIBRATION:
            self.generateLuts()

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
        
        with open(os.path.join(self.saveLocation, 'LPM_Raw.csv'), 'w', newline='') as csvfile:
            rawOutputWriter = csv.writer(csvfile, delimiter=',')
            for pixelIdx, pixelTested in enumerate(exportData):
                rawOutputWriter.writerow([pixelIdx + 1] + [self.laserTestStatus[pixelIdx]] + list(pixelTested))
        self.logger.addNewLog("Raw data saved to the tmp folder and " + self.saveLocation)

    
    
    ## Creating the dataframe for the process team and the database team
    ## Dataframe headers are ["DateTime", "Factory", "Machine", "TestType", "Pixel", "Rack", "Laser", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation"]
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
                pulseChangeIndexes.insert(0, 0)
                pulseChangeIndexes.append(len(pixelrawdata) + 1)
                pulseSplitData.append([pixelrawdata[pulseChangeIndexes[idx]:pulseChangeIndexes[idx+1]] for idx in range(len(pulseChangeIndexes)-1)])
        avg_daq_p_data = np.array([[stat.mean(pixelData[levelNum]) if (levelNum < len(pixelData) and len(pixelData[levelNum]) > 0)  else np.NaN for levelNum in range(len(commandedPowerLevels))] for pixelData in pulseSplitData]).round(decimals=3)
        std_daq_p_data = np.array([[stat.stdev(pixelData[levelNum]) if (levelNum < len(pixelData) and len(pixelData[levelNum]) > 1) else np.NaN for levelNum in range(len(commandedPowerLevels))] for pixelData in pulseSplitData]).round(decimals=3)
        dev_daq_p_data = np.array([[self.percentDiff(pulseAvgData, commandedPowerLevels[pulseNum]) if (not np.isnan(pulseAvgData)) else np.NaN for pulseNum, pulseAvgData in enumerate(pixelData)] for pixelData in avg_daq_p_data]).round(decimals=3)
        outputData = []
        for pixelIdx, data in enumerate(self.laserTestData):         
            for powerLevelNum, powerLevelData in enumerate(avg_daq_p_data[pixelIdx]):
                #["DateTime", "Factory", "Machine", "TestType", "Pixel", "Rack", "Laser", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation"]
                if self.laserTestStatus[pixelIdx] != 5:
                    commandedPower = round(commandedPowerLevels[powerLevelNum], 2)
                else:
                    commandedPower = np.nan
                if len(pulseSplitData[pixelIdx]) > powerLevelNum:
                    numDataPoints = len(pulseSplitData[pixelIdx][powerLevelNum])
                else:
                    numDataPoints = 0
                if pixelIdx < (self.laserSettings.numberOfPixels):
                    outputData.append([self.timeStamp.strftime("%Y-%m-%d, %H:%M:%S"), MachineSettings._machineID, MachineSettings._factoryID, self.testTypesAsString[self.testSettings._testType], pixelIdx + 1, self.laserSettings.vfpMap[pixelIdx][2], self.laserSettings.vfpMap[pixelIdx][3], dev_daq_p_data[pixelIdx][powerLevelNum] < 5, self.testStatusTable[self.laserTestStatus[pixelIdx]], commandedPower, avg_daq_p_data[pixelIdx][powerLevelNum], std_daq_p_data[pixelIdx][powerLevelNum], dev_daq_p_data[pixelIdx][powerLevelNum], numDataPoints])
        cols =["Date", "Machine ID", "Factory ID", "Test Type", "Pixel", "Rack", "Laser", "Process Acceptance", "Status", "Commanded Power", "Pulse Power Average", "Pulse Power Stdv", "Pulse Power Deviation", "Data Points"] # add rack and laser printer name, name of test(CVER, DVER....), timestamp  
        self.results = pd.DataFrame(outputData, columns=cols)
        self.results.to_csv(os.path.join("tmp", "LPM_processed.csv"), index=False)
        self.results.to_csv(os.path.join(self.saveLocation, "LPM_processed.csv"), index=False)
        validRanges = ["ValidRanges"]
        validRanges.append(self.getValidPixelRanges())
        with open(os.path.join(self.saveLocation, 'summary.csv'), 'w', newline='') as summaryFile:
            writer = csv.writer(summaryFile)
            writer.writerows(self.getSummary())
            writer.writerow(validRanges)
        return self.results

    def getSummary(self):
        summary = self.results.groupby("Commanded Power", as_index=False)[['Pulse Power Average', "Pulse Power Stdv", "Pulse Power Deviation"]].mean()
        summary = np.round_(summary.to_numpy(), decimals=3).astype('str')
        summary = np.insert(summary, 0, ['Commanded Power', 'Total Power Average', 'Total Average Power Stdv', 'Total Average Power Deviation'], axis=0).tolist()
        return summary
    
    def getValidPixelRanges(self):
        passedPixels = self.results.loc[self.results["Status"] == "Passed"]["Pixel"].to_numpy()
        validRanges = []
        startRange = 1
        for pixel in range(1, self.laserSettings.numberOfPixels+1):
            if pixel not in passedPixels and startRange is not None:
                validRanges.append([startRange, pixel-1])
                startRange = None
            elif startRange is None and pixel in passedPixels:
                startRange = pixel
        return validRanges


    def generateLuts(self):
        luts = self._lutDataManager.convertLaserDataToLUTData(self.laserTestData, self.commandedPowerData, self.laserTestStatus, self.testSettings._CalId, self.laserSettings, saveLocation=self.saveLocation)
        bins = self._lutDataManager.convertLUTDataToBinaries(luts)

    def uploadLinearLuts(self):

        # lutExistsStatus = [True for VFLCR in MachineSettings._vflcrIPs]
        # start = now = time.time()
        
        # while(any(lutExistsStatus)):
            
        #     # timeout after 10s, exit without telling the plc we finished
        #     now = time.time()
        #     if ((now - start) > 10): 
        #         print("Timed out waiting for VFLCR LUTs to empty")
        #         return
            
        #     for vflcrNum, vflcrIP in enumerate(MachineSettings._vflcrIPs):
        #         lutExistsStatus[vflcrNum] = not FTP_Manager.lutsEmpty(vflcrIP)

        self._lutDataManager.uploadLinearLuts(self.laserSettings)
        self.LUTsUploadedTag.setPlcValue(True)


    def uploadCalibratedLuts(self, calibrationID:int):
        
        self.logger.addNewLog("Writing binaries to folders and printer.......")
        
        binpath = os.path.join(self.saveLocation, "bin")
        self._lutDataManager.writeBinariesToFolder(calibrationID, self.laserSettings, binPath=binpath)
        
        # lutExistsStatus = [True for VFLCR in MachineSettings._vflcrIPs]
        # start = now = time.time()
        
        # while(any(lutExistsStatus)):
            
        #     # timeout after 10s, exit without telling the plc we finished
        #     now = time.time()
        #     if ((now - start) > 10): 
        #         print("Timed out waiting for VFLCR LUTs to empty")
        #         return
            
        #     for vflcrNum, vflcrIP in enumerate(MachineSettings._vflcrIPs):
        #         lutExistsStatus[vflcrNum] = not FTP_Manager.lutsEmpty(vflcrIP)

        os.makedirs(binpath, exist_ok=True)
        self.logger.addNewLog("Binaries written to folder complete")

        self._lutDataManager.writeBinaryArraysToVFPLCs(calibrationID, self.laserSettings)
        self.logger.addNewLog("Binaries written to printer complete")

        self.LUTsUploadedTag.setPlcValue(True)

    ## Example Command
    def exampleCommand(self):
        camera = CameraDriver()
        #self.targetPostion = 100
        #camera.moveRelPositioner(self.targetPostion)
        #camera.moveAbsPositioner(self.targetPostion)
        #camera.homePositioner()
        #self.ZaberPositionTag.setPlcValue(camera.getPositionerPosition())
        #self.ZaberHomedTag.setPlcValue(camera.getPositionerRefStatus())
        self.exampleResultTag.setPlcValue(1)

    def initializeCalibration(self): 
        self.logger.addNewLog("Starting test")

        #TODO: link plc pulse settings to power limits
        # overwrite test settings from plc values
        self.testSettings._pulseOnMsec = self.pulseOnMsecTag.value
        self.testSettings._numPulsesPerLevel = self.numPulsesPerLevelTag.value
        self.testSettings._startingPowerLevel = self.startingPowerLevelTag.value
        self.testSettings._numPowerLevelSteps = self.numPowerLevelStepsTag.value
        self.testSettings._powerLevelIncrement = self.powerLevelIncrementTag.value
        self._lutDataManager.changeTestSettings(self.testSettings) 

        # read test type
        self.testType = TestType(self.TestTypeTag.value)
        self.testSettings._tolerancePercent = testTolerancePercents[self.testType] # this is not used by LUT generation, so setting it after changing LUT test settings is OK

        self.timeStamp = datetime.utcnow()
        
        if MachineSettings._simulation:
            self.saveLocation = os.path.join(".", "tmp", "output")
            self.resultsLocation = os.path.join(".", "tmp", "results")
        else:
            self.saveLocation = self._createoutputdirectory()
            os.makedirs(self.saveLocation)
            self.resultsLocation = self.saveLocation + "_RESULTS"
            os.makedirs(self.resultsLocation, exist_ok=True) # This directory shouldn't already exist, but crashing is probably more of a hassle than it's worth

        # Get pixel mapping
        self.laserSettings.vfpMap = self.vfpMapTag.value

        self.createLogFile()
        self.results = None
        self.laserTestData = [[] for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with power measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestEnergy = [[] for pixel in range(self.laserSettings.numberOfPixels)] ##Data array that is populated during a test with energy measurements and postprocessed for later analysis. This array is consumed after data is saved.
        self.laserTestStatus = [5 for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with post test pixel status and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerData = [[] for pixel in range(self.laserSettings.numberOfPixels)] ## Data array that is populated during a test with commmanded Power Data(W) and postprocessed for later analysis. This array is consumed after data is saved.
        self.commandedPowerLevels = [] ## Array generated with the power levels derived from processing commanded power data

      #  if not self.camera.isConnected:
      #  self.camera.initialize()
        
        self.calibrationInitializedTag.setPlcValue(1)

    def initializePixel(self):
        print("initializePixel()")

        print("Active Pixel: " + str(self.activePixelTag.value))

        if self.activePixelTag.value == 0:
            print("Active pixel is 0 which isn't really a thing so this is going to end up writing the data for this pixel as the last pixel :shrug:")

        ## update exposure counter, set starting exposure
        #self.currentPowerLevelIndex = 0
        #self.updateExposure(self.currentPowerLevelIndex)

        if self.pyrometer.isConnected:
            print("pyrometer: connected")
            print("pyrometer: clearing buffer")
            self.pyrometer.clearData()
            print("pyromter: starting streaming")
            self.pyrometer.startDataCollection()
            self.pixelInitializedTag.setPlcValue(1)
        else:
            print("pyromter: failed - not connected")

    def capturePixel(self):
        print("capturePixel()")

        pyroDataCaptured = self._capturePowerData()

        print("\npyroDataCaptured: " + str(pyroDataCaptured))
        
        # let the cmd timeout if we fail one of these
        if pyroDataCaptured:
            # success
            self.pixelCapturedTag.setPlcValue(1)
        else:
            print("pixel power capture failed")
            self.errorCaptureFailedTag.setPlcValue(1)

    def captureFrame(self):
        print("captureFrame()")

        frameCaptured = self._captureFrameData()

        #if self.currentPowerLevelIndex < self.numPowerLevelStepsTag.value:
            #update exposure for next power level if applicable
            #self.currentPowerLevelIndex += 1
            #self.updateExposure(self.currentPowerLevelIndex)

        print("\nframeCaptured: " + str(frameCaptured))
        
        # let the cmd timeout if we fail one of these
        if frameCaptured:
            # success
           self.FrameCaptureInstanceResponseTag.setPlcValue(self.CaptureFrameInstanceTag.value)
        else:
            print("Camera frame capture failed")
            self.errorFrameCaptureFailedTag.setPlcValue(1)

    def processPixel(self):
        print("processPixel()")
        self.pyrometer.endDataCollection()
        self.pyrometer.clearData()
        self.pixelResultTag.setPlcValue(1)  # autopass
        self.pixelProcessedTag.setPlcValue(1)

    def processCalibration(self):
        print("processCalibration()")
        self.endTest()
        self.calibrationProcessedTag.setPlcValue(1)
        
    def uploadTestData(self):
        print("uploadTestData()")
        success, bucketError = False, False
        retryNum = 1
        maxRetries = 1
        while (retryNum <= maxRetries) and not (success or bucketError):
            try:
                # Placeholder string vars
                endpoint = "TODO"
                access_key = "TODO"
                secret_key = "TODO"
                bucket = "TODO"
                local_filepath = os.path.join(self.saveLocation, "cameraData")
                S3_object_name = os.path.split(local_filepath)[-1]
                
                client = Minio(endpoint, access_key, secret_key)
                if not client.bucket_exists(bucket):
                    bucketError = True
                else:
                    client.fput_object(bucket, S3_object_name, local_filepath)
                    self.logger.addNewLog(f"Data from {local_filepath} uploaded to bucket {bucket} as {S3_object_name}")
                    success = True
            except (S3Error, urllib3.exceptions.MaxRetryError) as e:
                print(f"Upload attempt {retryNum} failed. Exception:\n{e}")
            finally:
                retryNum += 1 # always increment attempt number
        # check results of loop
        if success:
            ml_app_url = "TODO"
            presigned_download_url = client.get_presigned_url("GET", bucket, S3_object_name)
            self.http.request('POST', ml_app_url, presigned_download_url)
            self.testDataUploadedTag.setPlcValue(1)
        elif bucketError:
            self.logger.addNewLog(f"Failed to upload data from {local_filepath} to bucket {bucket} as {S3_object_name}")
            print(f"Upload failed. Bucket {bucket} not found.")
            self.errorBucketNotExistTag.setPlcValue(1)
        else: # error connecting to s3 without bucket not existing
            self.logger.addNewLog(f"Failed to upload data from {local_filepath} to bucket {bucket} as {S3_object_name}")
            self.errorS3ConnectionTag.setPlcValue(1)
    
    def downloadTestResults(self):
        print("downloadTestResults()")
        success, bucketError = False, False
        retryNum = 1
        maxRetries = 1
        while (retryNum <= maxRetries) and not (success or bucketError):
            try:
                # Placeholder string vars
                endpoint = "TODO"
                access_key = "TODO"
                secret_key = "TODO"
                bucket = "TODO"
                local_filepath = self.resultsLocation
                S3_object_name = os.path.split(local_filepath)[-1]
                
                client = Minio(endpoint, access_key, secret_key)
                if not client.bucket_exists(bucket):
                    bucketError = True
                else:
                    client.fget_object(bucket, S3_object_name, local_filepath)
                    self.logger.addNewLog(f"S3 object {S3_object_name} downloaded from bucket {bucket} to {local_filepath}")
                    success = True
            except (S3Error, urllib3.exceptions.MaxRetryError) as e:
                print(f"Download attempt {retryNum} failed. Exception:\n{e}")
            finally:
                retryNum += 1 # always increment attempt number
        # check results of loop
        if success:
            self.testResultsDownloadedTag.setPlcValue(1)
        elif bucketError:
            self.logger.addNewLog(f"Failed to download S3 object {S3_object_name} from bucket {bucket} to {local_filepath}")
            print(f"Download failed. Bucket {bucket} not found.")
            self.errorBucketNotExistTag.setPlcValue(1)
        else: # error connecting to s3 without bucket not existing
            self.logger.addNewLog(f"Failed to download S3 object {S3_object_name} from bucket {bucket} to {local_filepath}")
            self.errorS3ConnectionTag.setPlcValue(1)

    
    def parseTestResults(self):
        ... # TODO: implement
        self.testResultsParsedTag.setPlcValue(1)
    
    ## Use this one function for a bunch of response resets if possible
    def resetResponseTags(self):
        self.exampleResultTag.setPlcValue(0)
        self.pixelResultTag.setPlcValue(0)
        self.calibrationInitializedTag.setPlcValue(0)
        self.pixelInitializedTag.setPlcValue(0)
        self.pixelCapturedTag.setPlcValue(0) 
        self.pixelProcessedTag.setPlcValue(0)
        self.calibrationProcessedTag.setPlcValue(0)
        self.LUTsUploadedTag.setPlcValue(0)
        self.testDataUploadedTag.setPlcValue(0)
        self.testResultsDownloadedTag.setPlcValue(0)
        self.testResultsParsedTag.setPlcValue(0)
        self.errorBucketNotExistTag.setPlcValue(0)
        self.errorS3ConnectionTag.setPlcValue(0)
        self.errorCaptureFailedTag.setPlcValue(0)
        self.errorFrameCaptureFailedTag.setPlcValue(0)
        self.MetaDataWriterReadyTag.setPlcValue(0)
        self.TestCompleteProcessedTag.setPlcValue(0)
        self.TestAbortProcessedTag.setPlcValue(0)

    ##################################### TAG REACTIONS ###################################################################

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

    def captureFrameReaction(self):
        cmd = self.captureFrameTag.value
        if cmd == True:
            self.logger.addNewLog("Capture Frame command received from  PLC ")
            self.captureFrame()
        if cmd == False:
            self.resetResponseTags()        

    def processPixelReaction(self):
        cmd = self.processPixelTag.value
        if cmd == True:
            self.logger.addNewLog("Process pixel command received from  PLC ")
            self.processPixel()
        if cmd == False:
            self.resetResponseTags()

    def processCalibrationReaction(self):
        cmd = self.processCalibrationTag.value
        if cmd == True:
            self.logger.addNewLog("Process calibration command received from  PLC ")
            self.processCalibration()
        if cmd == False:
            self.resetResponseTags()

    def initializeCalibrationReaction(self):
        cmd = self.initializeCalibrationTag.value
        if cmd == True:
            self.logger.addNewLog("Initialize calibration command received from  PLC ")
            self.initializeCalibration()
        if cmd == False:
            self.resetResponseTags()

    def uploadLinearLUTsReaction(self):
        cmd = self.UploadLinearLUTsTag.value
        if cmd == True:
            self.logger.addNewLog("Upload linear LUTs command received from  PLC ")
            self.uploadLinearLuts()
        if cmd == False:
            self.resetResponseTags()

    def uploadCalibratedLUTsReaction(self):
        cmd = self.UploadCalibratedLUTsTag.value
        if cmd == True:
            self.logger.addNewLog("Upload calibrated LUTs command received from  PLC ")
            self.uploadCalibratedLuts(self.CurrentLUTIDTag.value+1)
        if cmd == False:
            self.resetResponseTags()
    
    def uploadTestDataReaction(self):
        cmd = self.uploadTestDataTag.value
        if cmd == True:
            self.logger.addNewLog("Upload test data command received from  PLC ")
            self.uploadTestData()
        if cmd == False:
            self.resetResponseTags()
    
    def downloadTestResultsReaction(self):
        cmd = self.downloadTestResultsTag.value
        if cmd == True:
            self.logger.addNewLog("Download test results command received from  PLC ")
            self.downloadTestResults()
        if cmd == False:
            self.resetResponseTags()
        
    def parseTestResultsReaction(self):
        cmd = self.parseTestResultsTag.value
        if cmd == True:
            self.logger.addNewLog("Parse test results command received from  PLC ")
            self.parseTestResults()
        if cmd == False:
            self.resetResponseTags()

    def ZaberHomeReaction(self):
        cmd = self.ZaberHomeTag.value
        if cmd == True:
            self.logger.addNewLog("Zaber home command received from  PLC ")
            camera = CameraDriver()
            camera.homePositioner()
            self.camera.initialize(self.gd)
            #Check camera directory
            self.camera_dir = os.path.join(self.saveLocation, "cameraData")
            if not os.path.exists(self.camera_dir):
                os.makedirs(self.camera_dir, exist_ok=True)
            # Meta Writer Init
            time_start = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ%f')
            self.metadatafilewriter = MetadataFileWriter(machine=self.MachineNameTag.value, datetime=time_start)
            self.MetaDataWriterReadyTag.setPlcValue(1)
        if cmd == False:
            self.resetResponseTags()

    def ZaberMoveRelativeReaction(self):
        cmd = self.ZaberMoveRelativeTag.value
        if cmd == True:
            self.logger.addNewLog("Zaber move relative command received from  PLC ")
            camera = CameraDriver()
            camera.moveRelPositioner(self.ZaberRelativePosParTag.value)
        if cmd == False:
            self.resetResponseTags()

    def ZaberMoveAbsoluteReaction(self):
        cmd = self.ZaberMoveAbsoluteTag.value
        if cmd == True:
            self.logger.addNewLog("Zaber move absolute command received from  PLC ")
            camera = CameraDriver()
            camera.moveAbsPositioner(self.ZaberAbsolutePosParTag.value)
            self.camera.setExposure(self.CameraExposureTag.value,self.gd) # Set Exposure with zaber move 
        if cmd == False:
            self.resetResponseTags()

    def ZaberGetHomeStatusReaction(self):
        cmd = self.ZaberGetHomeStatusTag.value
        if cmd == True:
            self.logger.addNewLog("Zaber get home status command received from  PLC ")
            camera = CameraDriver()
            self.ZaberHomedTag.setPlcValue(camera.getPositionerRefStatus())
        if cmd == False:
            self.resetResponseTags()

    def ZaberGetPosFeedbackReaction(self):
        cmd = self.ZaberGetPosFeedbackTag.value
        if cmd == True:
            self.logger.addNewLog("Zaber get position feedback command received from  PLC ")
            camera = CameraDriver()
            self.ZaberPositionTag.setPlcValue(camera.getPositionerPosition())
        if cmd == False: 
            self.resetResponseTags()

    def OMSTestCompleteReaction(self):
        cmd = self.OMSTestCompleteTag.value
        if cmd == True:
            self.metadatafilewriter.save_file(self.camera_dir, test_status='Completed')
            self.TestCompleteProcessedTag.setPlcValue(1)
        if cmd == False:   
            self.resetResponseTags()

    def OMSTestAbortedReaction(self):
        cmd = self.OMSTestAbortedTag.value
        if cmd == True:
            print(f'saving metadata json to {self.camera_dir}')
            self.metadatafilewriter.save_file(self.camera_dir, test_status='Aborted')
            print(f'saved metadata json to {self.camera_dir}')
            self.TestAbortProcessedTag.setPlcValue(1)

        if cmd == False:   
            self.resetResponseTags()

   ############################## HELPER FUNCTION ##########################################
    def _is_image_new(self,  new_img):
        if self._last_captured_frame is None:
            self._last_captured_frame = new_img
            return True
        else:
            if np.array_equal(self._last_captured_frame, new_img):
                return False
            else:
                self._last_captured_frame = new_img
                return True

    def _captureFrameData(self):
        print("_captureFrameData()")

        camera = CameraDriver()
        activePixel = self.activePixelTag.value
        gantryXPosition = self.GantryXPositionStatusTag.value
        gantryYPosition = self.GantryYPositionStatusTag.value
        zaberPosition = camera.getPositionerPosition()
        pulseOnMsec = self.pulseOnMsecTag.value
        CurrentPowerLevel = self.currentPowerWattsTag.value
        machineName = self.MachineNameTag.value

        metadata, imageData = self.camera.fetchFrame(activePixel,gantryXPosition,gantryYPosition,zaberPosition,pulseOnMsec,CurrentPowerLevel,machineName,self.gd)

        if metadata is None or imageData is None:
            return False
        else:
            is_image_new = self._is_image_new(imageData) #declare fault
            # Save image to camera-specific subdirectory until otherwise specified. Append to metadata (in memory)
            metadata.update({'frame_is_a_duplicate': not is_image_new})
            image_url = None  ##TODO - get image URL from S3
            metadata_write_status = self.metadatafilewriter.add_frame_and_save_image(metadata, imageData, self.camera_dir,image_url)

            print(f"Saved frame to: {os.path.join(self.camera_dir, self.metadatafilewriter.current_image_filename)}")
            return True
          

    def _capturePowerData(self):
        
        print("_capturePowerData()")
        if self.pyrometer.isConnected:

            pulses = self.pyrometer.getFullData()

            print("\ndata: [ ")
            for pulse in pulses:
                for datum in pulse:
                    print(str(datum) + ", ")
                print(";")
            print("]")

            pulsePeak = self.pyrometer.getFullDataPeak(update=False)
            print("\npulsePeak: " + str(pulsePeak[0]))

            allPulsesOkay = True   # group status
            lastError = 0

            self.pyrometer.clearData()
            
            measuredPowerMax = 0 # reset max 

            for pulse in pulses:

                energy = pulse[0] * self._PyroMultiplicationFactor
                timestamp = pulse[1]
                status = pulse[2]

                # throw out pulses with non-zero status
                # TODO: figure out why we're getting pulses with non-zero status
                if (status == 0):
                    measuredPower = energy/(self.testSettings._pulseOnMsec / 1000)
                    measuredEnergy = energy
                    expectedPower = self.currentPowerWattsTag.value

                    # append data for each pulse
                    self.laserTestData[self.activePixelTag.value - 1].append(measuredPower)
                    self.laserTestEnergy[self.activePixelTag.value - 1].append(measuredEnergy)
                    self.commandedPowerData[self.activePixelTag.value - 1].append(expectedPower)

                    measuredPowerMax = max([measuredPower , measuredPowerMax])
                    measuredPowerMax = measuredPowerMax

                    # evaluate the variable formerly known as testStatus
                    # check the power of each pulse but only report 1 status per pixel
                    # test status meaning: ["In Progress", "Passed", "High Power Failure", "Low Power Failure", "No Power Failure", "Untested", "", "", "", "", "Abort"]
                    if measuredPower > (expectedPower * (1 + self.testSettings._tolerancePercent/100)):
                        # high power
                        lastError = 2
                        allPulsesOkay = False
                    elif measuredPower < (expectedPower * (1 - self.testSettings._tolerancePercent/100)):
                        # low power
                        lastError = 3
                        allPulsesOkay = False
                    elif measuredPower < (expectedPower * 0.05):
                        # no power
                        lastError = 4
                        allPulsesOkay = False
                        
            self.MeasuredPowerTag.setPlcValue(measuredPowerMax) 
            self.CommandedPowerTag.setPlcValue(self.currentPowerWattsTag.value)

            if allPulsesOkay:
                # pixel pass
                self.laserTestStatus[self.activePixelTag.value - 1] = 1
                self.LaserTestStatusTag.setPlcValue(1)
            else:
                self.laserTestStatus[self.activePixelTag.value - 1] = lastError
                self.LaserTestStatusTag.setPlcValue(lastError)
            return True
        
        else:
            
            return False
        
    def updateExposure(self, powerLevelIndex):
        
        nextPowerWatts = self.startingPowerLevelTag.value + (self.powerLevelIncrementTag.value * powerLevelIndex)
        maxExposureTime = self.pulseOnMsecTag.value * 1.1

        if nextPowerWatts != 0:
            exposure = self.exposureAt100W / (nextPowerWatts / 100)     ## when power doubles, exposure halves
        else:
            print("Next power is zero, falling back to default")
            exposure = self.exposureAt100W

        if exposure > (maxExposureTime):
            print("Exposure longer than 110% pulse on time - limiting")
            exposure = maxExposureTime

        print("setting exposure to " + str(exposure) + "ms")
        
        status = self.camera.setExposure(exposure,self.gd)

        print("status: " + str(status))
       
    def _createoutputdirectory(self):
        date = self.timeStamp.strftime("%Y%m%d")
        machineID = str(MachineSettings._machineID)[0:2] + str(MachineSettings._machineID[2:]).zfill(2)
        if(self.testType == TestType.LOW_POWER_CHECK):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(".", "tmp", "printerinfo", MachineSettings._factoryID, machineID, "Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_LOWPOWER")
            self.testName = machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_LOWPOWER"
        elif(self.testType == TestType.CALIBRATION):    
            calID = self.testSettings._CalId  
            drivePath = os.path.join(".", "tmp", "printerinfo", MachineSettings._factoryID, machineID, "Laser Data", "30_Calibrations", machineID + "_LUT_" + str(calID).zfill(5)+"_" + date)
            self.testName = machineID + "_LUT_" + str(calID).zfill(5)+"_" + date + " Calibration"
        elif(self.testType == TestType.CLEAN_POWER_VERIFICATION):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(".", "tmp", "printerinfo", MachineSettings._factoryID, machineID, "Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_CVER")
            self.testName = machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_CVER"
        elif(self.testType == TestType.DIRTY_POWER_VERIFICATION):
            time = self.timeStamp.strftime("%H%M")
            calID = self.CurrentLUTIDTag.value
            drivePath = os.path.join(".", "tmp", "printerinfo", MachineSettings._factoryID, machineID, "Laser Data", "40_Verifications", machineID + "-" + date + "-" + time + "-LUT-" + str(calID).zfill(5)+"_DVER")
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

