import wx
import wx.lib.activex

class CameraDriver:
    
    def __init__(self):
        self.app = wx.App()
        self.frame = wx.Frame( parent=None, id=wx.ID_ANY,size=(900,900), 
                              title='Python Interface to DataRay')
        p = wx.Panel(self.frame,wx.ID_ANY) # TODO: is this actually necessary?
        #Get Data
        self.gd = wx.lib.activex.ActiveXCtrl(p, 'DATARAYOCX.GetDataCtrl.1')
        # Run initialization routine on object creation
        self.initialize()
    
    def initialize(self):
        self.gd.ctrl.StopDevice()
        self.gd.ctrl.StartDriver()
        self.gd.ctrl.ResetCamera(0)
        # Set resolution and ROI before starting device
        self.gd.ctrl.SetResolutionAndROI(1, 0, 0, 2048, 2048) # FullResolution=Yes, Left=Top=0, Width=Height=2048
        self.gd.ctrl.StartDevice()
        self.gd.ctrl.GetSoftwareVersion() # 8.0D92 is expected here
        #self.gd.ctrl.LoadThisJobFile('TODO: Add This Filepath')
        self.gd.ctrl.GetCameraNID(0)
    
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
        # if Error, re-initialize and set trigger mode = 3, exposure = 2.5ms, and gain = 1.0
        # TODO: are these reasonable/correct values to be using?
        if not deviceOK:
            self.initialize()
            self.setTriggerMode(3)
            self.setExposureAndGain(2.5, 1.0)
        newFrame = dict()
        newFrame['Exposure'] = self.getExposure()
        newFrame['Gain'] = self.getGain()
        newFrame['FullRes'] = self.gd.ctrl.CaptureIsFullResolution()
        newFrame['HRes'] = self.gd.ctrl.GetHorizontalPixels()
        newFrame['VRes'] = self.gd.ctrl.GetVerticalPixels()
        newFrame['RawData'] = self.gd.ctrl.GetWinCamDataAsVariant()
        # Convert WinCamData to 2D array of 16 bit unsigned integers
        # TODO: compare to previous and ignore if identical
        ...
    