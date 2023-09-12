# Set some laser info based on the machine 
# TODO: this should probably be condensed into just a VFPMap class
class LaserSettings:

    def __init__(self) -> None:
        # this should get populated by the model at initializeCalibration()
        self._vfpMap = [[]] # [[Pixel, Enable, Rack, Laser],........]

    @property
    def vfpMap(self):
        return self._vfpMap
    
    @property
    def numberOfPixels(self):
        return len(self._vfpMap)

    @vfpMap.setter
    def vfpMap(self, pixelMap):
        self._vfpMap = [ pixel.copy() for pixel in pixelMap ]

        