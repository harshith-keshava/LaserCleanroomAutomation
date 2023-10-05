
import png
import time
import numpy as np
import json
from datetime import datetime
import zaber.serial
import wx
import wx.lib.activex


class CameraDriver:
    
    def zaberConnect(self):
        ZaberConnect = zaber.serial.AsciiSerial("COM11")
        return ZaberConnect
    
    def initialize(self,gdCtrl, exposure=1.0, gain=1.0, triggerMode=3, fullResolution=1, topLeft=(0,0), dimensions=(2048,2048)): #dimensions= (width, height)
        gdCtrl.ctrl.StopDevice()
        gdCtrl.ctrl.StartDriver()
        gdCtrl.ctrl.ResetCamera(0)
        # Set resolution and ROI before starting device
        gdCtrl.ctrl.SetResolutionAndROI(fullResolution, *topLeft, *dimensions) 
        self.isConnected = gdCtrl.ctrl.StartDevice()
        if self.isConnected:
            self.setTriggerMode(triggerMode,gdCtrl)
            gdCtrl.ctrl.AutoShutterOn = False # Disable automatic exposure setting; mostly relevant for using mode 0 (freerun)
            self.setExposureAndGain(exposure, gain,gdCtrl)
            self.softwareVersion = gdCtrl.ctrl.GetSoftwareVersion() # 8.0D92 is expected here
            #gdCtrl.ctrl.LoadThisJobFile('ConfigFiles\wincam_settings.ojf')
            self.cameraNID = gdCtrl.ctrl.GetCameraNID(0)
        else:
            print("An error occurred initializing camera. Check Camera connection is ok")    
    
    def getTriggerMode(self,gdCtrl):
        return gdCtrl.ctrl.LCMTriggerMode
        
    def setTriggerMode(self, triggerMode,gdCtrl):
        gdCtrl.ctrl.LCMTriggerMode = triggerMode
        return gdCtrl.ctrl.LCMTriggerMode==triggerMode
    
    def setExposureAndGain(self, newExposure, newGain,gdCtrl):
        # Propagate success of both setters
        return self.setExposure(newExposure,gdCtrl) and self.setGain(newGain,gdCtrl)

    def getExposure(self,gdCtrl):
        return gdCtrl.ctrl.GetTargetCameraExposure(0)
        
    def setExposure(self, newExposure,gdCtrl):
        gdCtrl.ctrl.SetTargetCameraExposure(0, newExposure)
        return gdCtrl.ctrl.GetTargetCameraExposure(0)==newExposure
    
    def getGain(self,gdCtrl):
        return gdCtrl.ctrl.GetTargetCameraGain(0)
        
    def setGain(self, newGain,gdCtrl):
        gdCtrl.ctrl.SetTargetCameraGain(0, newGain)
        return gdCtrl.ctrl.GetTargetCameraGain(0)==newGain
    
    def fetchFrame(self,activePixel,gantryXPosition,gantryYPosition,zaberPosition,pulseOnMsec,startingPowerLevel,machineName,gdCtrl):
        # Get a new frame cluster containing:
        # Com Error, Exposure, Gain, Full Res, H Res, V Res, and 2D Image.
        deviceOK = gdCtrl.ctrl.StartDevice()
        # if Error, re-initialize with default values
        if not deviceOK:
            self.initialize()
            # TODO: I don't want to error here, but something should happen
            # assert self.isConnected, 'Failed to connect to camera; check hardware connection'
        
        metadata = dict()
        metadata['ActivePixel'] = activePixel
        metadata['GantryXPos'] = gantryXPosition
        metadata['GantryYPos'] = gantryYPosition
        metadata['ZaberPosition'] = zaberPosition
        metadata['PulseOnMsec'] = pulseOnMsec
        metadata['PowerLevel'] = startingPowerLevel
        metadata['MachineName'] = machineName
        metadata['CameraNID'] = self.cameraNID
        metadata['Exposure'] = self.getExposure()
        metadata['Gain'] = self.getGain()
        metadata['FullRes'] = gdCtrl.ctrl.CaptureIsFullResolution()
        metadata['HRes'] = gdCtrl.ctrl.GetHorizontalPixels()
        metadata['VRes'] = gdCtrl.ctrl.GetVerticalPixels()
        
        # Get timestamp and convert to various formats

        # Get current time in UTC
        time_utc = datetime.utcnow()

        metadata['TimeString'] = time_utc.strftime('%Y%m%dT%H%M%SZ%f')

        # Convert WinCamData tuple to 2D numpy array
        rawData = gdCtrl.ctrl.GetWinCamDataAsVariant()
        imageData = np.array(rawData, dtype=np.uint16)
        if metadata['VRes']*metadata['HRes'] == len(rawData):
            imageData = imageData.reshape((metadata['VRes'], metadata['HRes'])) # (numRows, numCols)
        else:
            imageData = imageData.reshape((1,-1)) # (numRows=1, numCols=any); if there's a mismatch in rows/cols for any reason, one row will at least contain everything. TODO: does image processing hate this?
        
        return metadata, imageData
    
    

    def moveAbsPositioner(self,target_position):
        try:
            Connection = zaber.serial.AsciiSerial("COM11")

            rawData = str(target_position * 1000000.0)  # Convert the value to a string. Conversion factor between disance and raw steps is 1000000
           
            # Concatenate "mov abs " with the rawData
            command_string = "move abs " + rawData
            
            print(command_string)

            # Send the "move absolute" command
            Connection.write(command_string)
            Connection.close()
            return 1

        except Exception as e:
            print("An error occurred:", e)
            return 0  #TO DO:  might want to return an appropriate error code

    def moveRelPositioner(self,target_position):
        try:
            Connection = zaber.serial.AsciiSerial("COM11")

            rawData = str(target_position * 1000000.0)  # Convert the value to a string. Conversion factor between disance and raw steps is 1000000
           
            # Concatenate "mov abs " with the rawData
            command_string = "move rel " + rawData  
            
            print(command_string)

            # Send the "move absolute" command
            Connection.write(command_string)
            Connection.close()
            return 1

        except Exception as e:
            print("An error occurred:", e)
            return 0  #TO DO:  might want to return an appropriate error code

    def homePositioner(self):
        try:
            Connection = zaber.serial.AsciiSerial("COM11")

            # Send the "home" command
            Connection.write("home")
            Connection.close()
            return 1

        except Exception as e:
            print("An error occurred:", e)
            return 0  #TO DO:  might want to return an appropriate error code

    def getPositionerPosition(self):
        try:
            Connection = zaber.serial.AsciiSerial("COM11")

            # Send the "get pos" command
            Connection.write("get pos")

            # Read status
            current_position_data = str(Connection.read())

            if len(current_position_data) >= 17:
                current_position = int(current_position_data[17:])
                current_position = current_position/1000000
                print(current_position) # in mm
                Connection.close()
                return current_position
            else:
                Connection.close()
                return 999.99

        except Exception as e:
            print("An error occurred:", e)
            return 999.99 #TO DO:  might want to return an appropriate error code

    def getPositionerRefStatus(self):
        try:
            Connection = zaber.serial.AsciiSerial("COM11")

            # Send the "get pos" command
            Connection.write("get pos")

            # Read status
            current_position_data = str(Connection.read())

            if len(current_position_data) >= 1:
                warning = str(current_position_data[14:16])
                print(warning)

                if warning == "WR" or warning == "WH" : # WR: no reference or WH: not homed
                    Connection.close()
                    return False
                else: 
                    Connection.close()
                    return True
            else:
                Connection.close()
                return 0 # TO DO: report error

        except Exception as e:
            print("An error occurred:", e)
            return 0 # TO DO: might want to return an appropriate error code       
      
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
