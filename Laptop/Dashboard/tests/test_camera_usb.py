"""Framing tests use memory only; no physical camera is opened."""
import io
from pathlib import Path
import sys
import time
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_usb import Camera, StreamStopped, receive_frame
import threading

JPEG = b'\xff\xd8\x00\x0a\x0d\xff\x00\xff\xd9'


def packet(data=JPEG, checksum=None, size=None, footer=b'\nEND FRAME\n', dimensions=b'320 HEIGHT=240'):
    return (b'FRAME TYPE=JPEG BYTES=' + str(size if size is not None else len(data)).encode()
            + b' CRC32=' + (checksum or f'{zlib.crc32(data):08X}').encode()
            + b' WIDTH=' + dimensions + b'\n' + data + footer)


class Fragmented(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2))


class CameraFramingTests(unittest.TestCase):
    def parse(self, data):
        return receive_frame(Fragmented(data), time.monotonic() + .03)

    def test_fragmented_binary_frame(self):
        data, meta = self.parse(packet())
        self.assertEqual(data, JPEG)
        self.assertEqual(meta['bytes'], len(JPEG))
        self.assertEqual((meta['width'], meta['height']), (320, 240))

    def test_reject_corrupt_checksum(self):
        with self.assertRaisesRegex(RuntimeError, 'checksum'): self.parse(packet(checksum='00000000'))

    def test_reject_oversize_before_reading_body(self):
        with self.assertRaisesRegex(RuntimeError, 'size'): self.parse(packet(size=524289))

    def test_reject_partial_frame(self):
        with self.assertRaisesRegex(RuntimeError, 'incomplete'): self.parse(packet()[:-16])

    def test_reject_missing_footer(self):
        with self.assertRaisesRegex(RuntimeError, 'footer'): self.parse(packet(footer=b'\nBAD\n'))

    def test_reject_non_jpeg_and_wrong_dimensions(self):
        with self.assertRaisesRegex(RuntimeError, 'JPEG'): self.parse(packet(data=b'not jpeg'))
        with self.assertRaisesRegex(RuntimeError, 'size'): self.parse(packet(dimensions=b'640 HEIGHT=480'))

    def test_camera_error_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, 'CAMERA_NOT_READY'): self.parse(b'ERROR CAMERA_NOT_READY\n')

    def test_stop_interrupts_a_waiting_usb_reader(self):
        stop=threading.Event(); stop.set()
        with self.assertRaises(StreamStopped):
            receive_frame(Fragmented(b''),time.monotonic()+3,stop)

    def test_slow_viewer_receives_latest_frame_without_backlog(self):
        camera=Camera()
        with camera.condition:
            camera.value.update(connected=True,sequence=100)
            camera.generation=3;camera.jpeg=JPEG
            camera.received_monotonic=time.monotonic()
        jpeg,meta=camera.wait_frame(1,3,timeout=0)
        self.assertEqual(meta['sequence'],100)
        self.assertEqual(jpeg,JPEG)
        self.assertIsNone(camera.wait_frame(100,3,timeout=0))
        self.assertIsNone(camera.wait_frame(1,2,timeout=0))

    def test_old_or_disconnected_frames_are_not_streamed(self):
        camera=Camera()
        camera.value.update(connected=True,sequence=1)
        camera.jpeg=JPEG;camera.received_monotonic=time.monotonic()-3
        self.assertIsNone(camera.wait_frame(0,0,timeout=0))
        self.assertFalse(camera.state()['streaming'])
        camera.value['connected']=False
        self.assertIsNone(camera.wait_frame(0,0,timeout=0))


if __name__ == '__main__': unittest.main()
