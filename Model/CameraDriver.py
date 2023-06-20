import wx
import wx.lib.activex
import png
import time
import numpy as np

class CameraDriver:
    
    def __init__(self):
        self.previousData = np.array((0,))
        self.app = wx.App()
        self.frame = wx.Frame( parent=None, id=wx.ID_ANY,size=(900,900), 
                              title='Python Interface to DataRay')
        p = wx.Panel(self.frame,wx.ID_ANY) # TODO: is this actually necessary?
        # Get Data
        self.gd = wx.lib.activex.ActiveXCtrl(p, 'DATARAYOCX.GetDataCtrl.1')
        # Set some parameters to avoid potential AttributeErrors on failed connection
        self.softwareVersion = ''
        self.cameraNID = 0
        # Run initialization routine on object creation
        self.initialize()
    
    def initialize(self, exposure=2.0, gain=1.0, triggerMode=3, fullResolution=1, topLeft=(0,0), dimensions=(2048,2048)): #dimensions= (width, height)
        self.gd.ctrl.StopDevice()
        self.gd.ctrl.StartDriver()
        self.gd.ctrl.ResetCamera(0)
        # Set resolution and ROI before starting device
        self.gd.ctrl.SetResolutionAndROI(fullResolution, *topLeft, *dimensions) 
        self.isConnected = self.gd.ctrl.StartDevice()
        if self.isConnected:
            self.setTriggerMode(triggerMode)
            self.gd.ctrl.AutoShutterOn = False # Disable automatic exposure setting; mostly relevant for using mode 0 (freerun)
            self.setExposureAndGain(exposure, gain)
            self.softwareVersion = self.gd.ctrl.GetSoftwareVersion() # 8.0D92 is expected here
            #self.gd.ctrl.LoadThisJobFile('ConfigFiles\wincam_settings.ojf')
            self.cameraNID = self.gd.ctrl.GetCameraNID(0)
    
    def getTriggerMode(self):
        return self.gd.ctrl.LCMTriggerMode
        
    def setTriggerMode(self, triggerMode):
        self.gd.ctrl.LCMTriggerMode = triggerMode
        assert self.gd.ctrl.LCMTriggerMode==triggerMode, 'Failed to set trigger mode'
    
    def setExposureAndGain(self, newExposure, newGain):
        # This class's setters check their own success, so no need to check again here
        self.setExposure(newExposure)
        self.setGain(newGain)

    def getExposure(self):
        return self.gd.ctrl.GetTargetCameraExposure(0)
        
    def setExposure(self, newExposure):
        self.gd.ctrl.SetTargetCameraExposure(0, newExposure)
        assert self.gd.ctrl.GetTargetCameraExposure(0)==newExposure, 'Failed to set exposure'
    
    def getGain(self):
        return self.gd.ctrl.GetTargetCameraGain(0)
        
    def setGain(self, newGain):
        self.gd.ctrl.SetTargetCameraGain(0, newGain)
        assert self.gd.ctrl.GetTargetCameraGain(0)==newGain, 'Failed to set gain'
    
    def fetchFrame(self):
        # Get a new frame cluster containing:
        # Com Error, Exposure, Gain, Full Res, H Res, V Res, and 2D Image.
        deviceOK = self.gd.ctrl.StartDevice()
        # if Error, re-initialize with default values
        if not deviceOK:
            self.initialize()
            assert self.isConnected, 'Failed to connect to camera; check hardware connection'
        newFrame = dict()
        newFrame['CameraNID'] = self.cameraNID
        newFrame['Exposure'] = self.getExposure()
        newFrame['Gain'] = self.getGain()
        newFrame['FullRes'] = self.gd.ctrl.CaptureIsFullResolution()
        newFrame['HRes'] = self.gd.ctrl.GetHorizontalPixels()
        newFrame['VRes'] = self.gd.ctrl.GetVerticalPixels()
        
        # Get timestamp and convert to various formats
        # To refactor for local time instead of GMT, use time.localtime instead of time.gmtime (same usage)
        newFrame['TimeSec'] = time.time()
        newFrame['TimeStruct'] = time.gmtime(newFrame['TimeSec'])
        newFrame['TimeString'] = time.asctime(newFrame['TimeStruct'])

        # Convert WinCamData tuple to 2D numpy array
        data = self.gd.ctrl.GetWinCamDataAsVariant()
        newFrame['Data'] = np.array(data).reshape((newFrame['VRes'], newFrame['HRes'])) # (numRows, numCols)
        
        # Check for stale frame using previous data
        newFrame['SameAsPrevious'] = (self.previousData.size == newFrame['Data'].size) and (self.previousData == newFrame['Data']).all()
        self.previousData = newFrame['RawData']
        
        # Check number of dimensions before making png so it doesn't error
        if newFrame['Data'].ndim == 2:
            # Create PNG from data array
            # Mode L is greyscale, aka Luminance/Lightness; 16 specifies bit depth (default is 8)
            newFrame['PNG'] = png.from_array(newFrame['Data'], mode='L;16')
            # PNG objects can be saved to file using .save(filename) or .write(openFileObject)
            # In general, you can only call save/write once; after it has been called the first time the PNG image is written, the source data will have been streamed, and cannot be streamed again.
        else:
            # There probably isn't data, so set PNG to None
            newFrame['PNG'] = None
        
        return newFrame
