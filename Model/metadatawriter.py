import os
import json
import datetime
from PIL import Image, PngImagePlugin

from vfomsprocessor import utils

class ImageWriter:
    def __init__(self, metadata_filename=None, machine=None, pixel_number=None, datetime=None,
                 gantry_x_mm=None, gantry_y_mm=None, zaber_z_mm=None, oms_calibration_info=None, image_filename=None):
        self.image_filename = image_filename
        self.metadata_filename = metadata_filename
        self.machine = machine
        self.pixel_number = pixel_number
        self.datetime = datetime
        self.gantry_x_mm = gantry_x_mm
        self.gantry_y_mm = gantry_y_mm
        self.zaber_z_mm = zaber_z_mm
        self.oms_calibration_info = oms_calibration_info
        self.metadata = None

    def load_image_filename(self, image_filename):
        _, machine, pixel, datestr = image_filename.split('.')[0].split('_')
        self.pixel_number = int(pixel.lower().split('p')[1])
        self.machine = machine
        self.datetime = datestr

    def create_image_filename(self):
        self.image_filename = create_image_filename(self.machine, self.pixel_number, self.datetime)

    def update_position(self, x, y, z):
        self.gantry_x_mm = x
        self.gantry_y_mm = y
        self.zaber_z_mm = z

    def load_calibration_info(self, fpath):
        self.oms_calibration_info = utils.load_metadata_from_file(fpath)

    def create_metadata(self):
        if self.datetime is None:
            utils.get_datestr()
        if self.image_filename is None:
            self.create_image_filename()
        self.metadata = {
            'image_filename': self.image_filename,
            'metadata_filename': self.metadata_filename,
            'machine': self.machine,
            'pixel_number': self.pixel_number,
            'datetime': self.datetime,
            'gantry_x_mm': self.gantry_x_mm,
            'gantry_y_mm': self.gantry_y_mm,
            'zaber_z_mm': self.zaber_z_mm,
            'oms_calibration_info': self.oms_calibration_info
        }

    def save_image(self, img, output_dir):
        if not type(img) == Image.Image:
            img_to_save = self.convert_array_to_PIL_image(img)
        else:
            img_to_save = img
        if self.metadata is None:
            self.create_metadata()
        if (type(self.metadata)==dict) and (os.path.exists(output_dir)):
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text('vf-oms-image-metadata', json.dumps(self.metadata))
            img_to_save.save(os.path.join(output_dir, self.image_filename),
                             "PNG",
                             pnginfo=pnginfo)

    def convert_array_to_PIL_image(self, img):
        return Image.fromarray(img.astype('uint16'))

def create_image_filename(machine, pixel_number, datetime=None):
    if datetime is None:
        datetime = utils.get_datestr()
    return f'OMS_{machine}_p{str(pixel_number).zfill(3)}_{datetime}.png'

class MetadataFileWriter:
    def __init__(self, machine=None, datetime=None, oms_calibration_info=None, metadata_filename=None):
        self.metadata_filename = metadata_filename
        self.machine = machine
        self.datetime_current = datetime
        self.datetime_start = datetime
        self.oms_calibration_info = oms_calibration_info
        self.metadata = None
        self.current_pixel = None
        self.current_image_filename = None
        self.current_frame = 0
        self.image_number = 0
        self.pixel_list = []
        self.frame_list = []

    def load_calibration_info(self, fpath):
        self.oms_calibration_info = utils.load_metadata_from_file(fpath)


    def add_frame_and_save_image(self, metadata, img, output_dir,
                                 image_url=None, datetime=None):

        self.add_frame(pixel_number, gantry_x_mm, gantry_y_mm, zaber_z_mm, datetime, image_url)
        iw = ImageWriter(self.metadata_filename, self.machine, self.current_pixel, self.datetime_current,
                 gantry_x_mm, gantry_y_mm, zaber_z_mm, self.oms_calibration_info, self.current_image_filename)
        iw.save_image(img, output_dir)

    def add_frame(self, pixel_number, gantry_x_mm, gantry_y_mm, zaber_z_mm, datetime=None, image_url=None):
        if self.current_pixel is None:
            self.current_pixel = pixel_number
        elif pixel_number != self.current_pixel:
            ## add frames from previous pixel
            self.add_pixel_info()
            self.frame_list = []
        self.create_frame_info(gantry_x_mm, gantry_y_mm, zaber_z_mm, datetime, image_url)

    def create_frame_info(self, gantry_x_mm, gantry_y_mm, zaber_z_mm, datetime=None, image_url=None):
        if datetime is None:
            self.datetime_current = utils.get_datestr()
        else:
            self.datetime_current = datetime
        if not self.datetime_start:
            self.datetime_start = self.datetime_current
        if not self.metadata_filename:
            self.create_metadata_filename(self.machine, self.datetime_start)
        frame_number = len(self.frame_list) + 1
        self.current_image_filename = create_image_filename(self.machine, self.current_pixel, self.datetime_current)
        frame_dict = {'frame_number': frame_number,
                     'image_filename': self.current_image_filename,
                     'image_url': image_url,
                     'datetime': self.datetime_current,
                     'gantry_x_mm': gantry_x_mm,
                     'gantry_y_mm': gantry_y_mm,
                     'zaber_z_mm': zaber_z_mm}
        self.frame_list.append(frame_dict)

    def update_pixel(self, pixel_number):
        self.current_pixel = pixel_number

    def add_pixel_info(self):
        self.pixel_list.append({
            'pixel_number': self.current_pixel,
            'frames': self.frame_list
        })

    def create_metadata_filename(self, machine, datetime_start):
        self.metadata_filename = f'OMS_{machine}_{datetime_start}.json'

    def create_metadata(self):
        self.metadata = {
            'metadata_filename': self.metadata_filename,
            'machine': self.machine,
            'datetime_start': self.datetime_start,
            'datetime_end': self.datetime_current,
            'number_pixels_tested': len(self.pixel_list),
            'oms_calibration_info': self.oms_calibration_info,
            'pixels': self.pixel_list
        }

    def save_file(self, output_dir):
        self.add_pixel_info() ## add info from the last pixel
        self.create_metadata()
        with open(os.path.join(output_dir, self.metadata_filename), 'w') as f:
            json.dump(self.metadata, f)

class CalibrationMetadataWriter:
    def __init__(self, lateral_mag, pyrometer_loss, boresight_angle_deg, z_offset_mm, oms_calibration_completed,
                 oms_calibration_due, calibration_filename=None):
        self.lateral_mag = lateral_mag
        self.pyrometer_loss = pyrometer_loss
        self.boresight_angle_deg = boresight_angle_deg
        self.z_offset_mm = z_offset_mm
        self.oms_calibration_completed = oms_calibration_completed
        self.oms_calibration_due = oms_calibration_due
        self.calibration_filename = calibration_filename

    def create_filename(self, datetime=None):
        if datetime is None:
            datetime = utils.get_datestr()
        self.calibration_filename = f'OMS-cal_{datetime}.json'

    def create_metadata(self):
        self.metadata = {
            'oms_calibration_filename': self.calibration_filename,
            'lateral_mag': self.lateral_mag,
            'pyrometer_loss': self.pyrometer_loss,
            'boresight_angle_deg': self.boresight_angle_deg,
            'z_offset_mm': self.z_offset_mm,
            'oms_calibration_completed': self.oms_calibration_completed,
            'oms_calibration_due': self.oms_calibration_due
        }

    def save_file(self, output_dir):
        if self.calibration_filename is None:
            self.create_filename()
        self.create_metadata()
        with open(os.path.join(output_dir, self.calibration_filename), 'w') as f:
            json.dump(self.metadata, f)


