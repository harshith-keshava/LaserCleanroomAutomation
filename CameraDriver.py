import wx
import wx.lib.activex
import png

class CameraDriver:
    
    def __init__(self):
        self.previousData = None
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
            #self.gd.ctrl.LoadThisJobFile('TODO: Add This Filepath')
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
        
        # Convert WinCamData to 2D array of 16 bit unsigned integers
        data = self.gd.ctrl.GetWinCamDataAsVariant()
        width, height = newFrame['HRes'], newFrame['VRes']
        newFrame['RawData'] = tuple(data[width*i:width*(i+1)] for i in range(height))
        
        # Check for stale frame using previous data
        newFrame['SameAsPrevious'] = self.previousData == newFrame['RawData']
        self.previousData = newFrame['RawData']
        
        try:
            # Create PNG from data array
            # Mode L is greyscale, aka Luminance/Lightness; 16 specifies bit depth (default is 8)
            newFrame['PNG'] = png.from_array(newFrame['RawData'], mode='L;16')
            # PNG objects can be saved to file using .save(filename) or .write(openFileObject)
            # In general, you can only call save/write once; after it has been called the first time the PNG image is written, the source data will have been streamed, and cannot be streamed again.
        except:
            # If PNG creation fails, it's almost certainly because there's no data yet. Also we don't want the function to fail, so just set None instead
            newFrame['PNG'] = None
        
        return newFrame
    