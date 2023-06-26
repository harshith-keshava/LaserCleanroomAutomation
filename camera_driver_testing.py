import time
from Model.CameraDriver import CameraDriver

if __name__ == '__main__':
    camera = CameraDriver()
    print('Camera is connected' if camera.isConnected else 'Camera is not connected')
    print('Current trigger mode: ', camera.getTriggerMode())
    print('Current exposure: ', camera.getExposure())
    print('Current gain: ', camera.getGain())
    print('Awaiting frame capture for 5 seconds...')
    time.sleep(5)
    print('Fetching and saving current frame data...')
    exampleFrame = camera.fetchFrame()
    exampleFrame.save('tmp/output/camera_driver_testing/exampleFrame', include_binary=True)