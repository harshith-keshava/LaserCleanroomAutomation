import os
import json
from datetime import datetime
from PIL import Image, PngImagePlugin

class ImageWriter:
    def __init__(self, image_filename, metadata_filename=None, metadata=None, oms_calibration_info=None):
        self.image_filename = image_filename
        self.metadata_filename = metadata_filename
        self.oms_calibration_info = oms_calibration_info
        self.metadata = self.update_metadata(metadata)

    def update_metadata(self, metadata):
        metadata_header = {
            'image_filename': self.image_filename,
            'metadata_filename': self.metadata_filename,
            'oms_calibration_info': self.oms_calibration_info
        }
        if metadata is not None:
            metadata_header.update(metadata)
        return metadata_header

    def save_image(self, img, output_dir):
        if not type(img) == Image.Image:
            img_to_save = self.convert_array_to_PIL_image(img)
        else:
            img_to_save = img
        if os.path.exists(output_dir):
            if self.metadata is None:
                img_to_save.save(os.path.join(output_dir, self.image_filename), "PNG")
            elif type(self.metadata) == dict:
                pnginfo = PngImagePlugin.PngInfo()
                pnginfo.add_text('vf-oms-image-metadata', json.dumps(self.metadata))
                img_to_save.save(os.path.join(output_dir, self.image_filename),
                                 "PNG",
                                 pnginfo=pnginfo)

    def convert_array_to_PIL_image(self, img):
        return Image.fromarray(img.astype('uint16'))


class MetadataFileWriter:
    def __init__(self, machine=None, datetime=None, oms_calibration_info=None, metadata_filename=None):
        self.metadata_filename = metadata_filename
        self.machine = machine
        self.datetime_start = datetime
        self.oms_calibration_info = oms_calibration_info
        self.metadata = None
        self.frame_list = []
        self.current_image_filename = None
        if not machine:
            self.machine = 'unknown'
        if not datetime:
            self.datetime_start = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ%f')
        if not metadata_filename:
            self.create_metadata_filename(self.machine, self.datetime_start)

    def load_calibration_info(self, fpath):
        self.oms_calibration_info = _load_metadata_from_file(fpath)

    def add_frame_and_save_image(self, metadata, img, output_dir,
                                 image_url=None):
        self.add_frame(metadata, image_url)
        iw = ImageWriter(self.current_image_filename, self.metadata_filename, metadata, self.oms_calibration_info)
        iw.save_image(img, output_dir)
        return True

    def add_frame(self, metadata, image_url=None):
        frame_number = len(self.frame_list) + 1
        machine = metadata['MachineName']
        pixel = metadata['ActivePixel']
        timestamp = metadata['TimeString']
        self.current_image_filename = self.create_image_filename(machine, pixel, timestamp)
        frame_dict = {'frame': frame_number,
                      'image_filename': self.current_image_filename,
                      'image_url': image_url}
        frame_dict.update(metadata)
        self.frame_list.append(frame_dict)

    def create_metadata_filename(self, machine, datetime_start):
        self.metadata_filename = f'OMS_{machine}_{datetime_start}.json'

    def create_image_filename(self, machine, pixel_number, datetime):
        return f'OMS_{machine}_p{str(pixel_number).zfill(3)}_{datetime}.png'

    def create_metadata(self, test_status='Aborted'):
        datetime_end = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ%f')
        self.metadata = {
            'metadata_filename': self.metadata_filename,
            'machine': self.machine,
            'datetime_start': self.datetime_start,
            'datetime_end': datetime_end,
            'test_status': test_status,
            'oms_calibration_info': self.oms_calibration_info,
            'frames': self.frame_list
        }

    def save_file(self, output_dir, test_status='Aborted'):
        self.create_metadata(test_status)
        with open(os.path.join(output_dir, self.metadata_filename), 'w') as f:
            json.dump(self.metadata, f)

def _load_metadata_from_file(fpath):
    try:
        with open(fpath) as f:
            return json.load(f)
    except Exception as e:
        print(e)
        return None
