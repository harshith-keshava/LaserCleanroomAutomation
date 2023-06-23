import wx
import wx.lib.activex
import png
import time
import numpy as np
import json

class CameraDriver:
    
    def __init__(self):
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
        return self.gd.ctrl.LCMTriggerMode==triggerMode
    
    def setExposureAndGain(self, newExposure, newGain):
        # Propagate success of both setters
        return self.setExposure(newExposure) and self.setGain(newGain)

    def getExposure(self):
        return self.gd.ctrl.GetTargetCameraExposure(0)
        
    def setExposure(self, newExposure):
        self.gd.ctrl.SetTargetCameraExposure(0, newExposure)
        return self.gd.ctrl.GetTargetCameraExposure(0)==newExposure
    
    def getGain(self):
        return self.gd.ctrl.GetTargetCameraGain(0)
        
    def setGain(self, newGain):
        self.gd.ctrl.SetTargetCameraGain(0, newGain)
        return self.gd.ctrl.GetTargetCameraGain(0)==newGain
    
    def fetchFrame(self):
        # Get a new frame cluster containing:
        # Com Error, Exposure, Gain, Full Res, H Res, V Res, and 2D Image.
        deviceOK = self.gd.ctrl.StartDevice()
        # if Error, re-initialize with default values
        if not deviceOK:
            self.initialize()
            # TODO: I don't want to error here, but something should happen
            # assert self.isConnected, 'Failed to connect to camera; check hardware connection'
        
        metadata = dict()
        metadata['CameraNID'] = self.cameraNID
        metadata['Exposure'] = self.getExposure()
        metadata['Gain'] = self.getGain()
        metadata['FullRes'] = self.gd.ctrl.CaptureIsFullResolution()
        metadata['HRes'] = self.gd.ctrl.GetHorizontalPixels()
        metadata['VRes'] = self.gd.ctrl.GetVerticalPixels()
        
        # Get timestamp and convert to various formats
        # To refactor for local time instead of GMT, use time.localtime instead of time.gmtime (same usage)
        metadata['TimeSec'] = time.time()
        metadata['TimeStruct'] = time.gmtime(metadata['TimeSec'])
        metadata['TimeString'] = time.asctime(metadata['TimeStruct'])

        # Convert WinCamData tuple to 2D numpy array
        rawData = self.gd.ctrl.GetWinCamDataAsVariant()
        imageData = np.array(rawData, dtype=np.uint16)
        if metadata['VRes']*metadata['HRes'] == len(rawData):
            imageData = imageData.reshape((metadata['VRes'], metadata['HRes'])) # (numRows, numCols)
        else:
            imageData = imageData.reshape((1,-1)) # (numRows=1, numCols=any); if there's a mismatch in rows/cols for any reason, one row will at least contain everything. TODO: does image processing hate this?
        
        return OmsFrame(metadata, imageData)

class OmsFrame:
    
    def __init__(self, metadata, framedata):
        self.metadata = metadata
        self.framedata = framedata
    
    def save(self, filename, include_binary=False):
        try:
            # Create PNG from frame data each time we want to save because each object can only be saved once (the object's data gets 'streamed' and is then spent)
            # Mode L is greyscale, aka Luminance/Lightness; 16 specifies bit depth (default is 8)
            png.from_array(self.framedata, mode='L;16').save(filename+'.png')
        except:
            pass # If it fails, we simply won't have a png due to not having valid image data
        
        with open(filename+'.json', 'w+') as f:
            json.dump(self.metadata, f)
        
        if include_binary:
            with open(filename+'.bin', 'w+b') as f:
                f.write(self.framedata.tobytes())
