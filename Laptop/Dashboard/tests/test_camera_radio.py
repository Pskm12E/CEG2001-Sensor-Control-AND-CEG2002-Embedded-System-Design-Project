import struct
import unittest
import zlib
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camera_radio import UsbMultiplexer

JPEG=b'\xff\xd8\nPONG FAKE\r\n\x00\xff\xd9'
def packet(jpeg=JPEG,crc=None):
    return f'VIDEO_FRAME BYTES={len(jpeg)} CRC32={zlib.crc32(jpeg) if crc is None else crc:08X} SEQ=25\n'.encode()+jpeg+b'\nEND_VIDEO\n'

class RadioMuxTests(unittest.TestCase):
    def test_fragmentation_never_exposes_jpeg_as_status(self):
        wire=b'PONG PICO_DESK_BRIDGE_V2\n'+packet()+b'STATUS valid\n'
        for chunk in (1,2,7,31,len(wire)):
            frames=[];bad=[];mux=UsbMultiplexer(lambda *data:frames.append(data),lambda:bad.append(True))
            for pos in range(0,len(wire),chunk):mux.feed(wire[pos:pos+chunk])
            self.assertEqual(list(mux.lines),['PONG PICO_DESK_BRIDGE_V2','STATUS valid'])
            self.assertEqual(frames[0][0],JPEG);self.assertEqual(frames[0][1],25)
            self.assertFalse(bad)
    def test_corrupt_frame_is_dropped_and_text_recovers(self):
        frames=[];bad=[];mux=UsbMultiplexer(lambda *data:frames.append(data),lambda:bad.append(True))
        mux.feed(packet(crc=0)+b'ROBOT STATE {}\n'+packet())
        self.assertEqual(len(bad),1);self.assertEqual(len(frames),1)
        self.assertEqual(list(mux.lines),['ROBOT STATE {}'])
    def test_overflow_and_bad_footer_rejected(self):
        for wire in (b'VIDEO_FRAME BYTES=32769 CRC32=00000000 SEQ=1\n',packet()[:-11]+b'INVALID!!!!',b'X'*4097):
            mux=UsbMultiplexer(lambda *data:None,lambda:None)
            with self.assertRaises(RuntimeError):mux.feed(wire)

if __name__=='__main__':unittest.main()
