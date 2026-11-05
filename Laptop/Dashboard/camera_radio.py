"""Continuous XIAO Wi-Fi video, received through the desk Pico's USB multiplexer."""
from collections import deque
import re
import threading
import time
import zlib

FRAME_HEADER=re.compile(rb'VIDEO_FRAME BYTES=(\d{1,5}) CRC32=([0-9A-F]{8}) SEQ=(\d{1,10})')
FOOTER=b'\nEND_VIDEO\n'


class UsbMultiplexer:
    """Binary frame payloads cannot be mistaken for robot text replies."""
    def __init__(self,publish,reject):
        self.buffer=bytearray();self.spec=None;self.lines=deque(maxlen=64)
        self.publish=publish;self.reject=reject

    def feed(self,data):
        self.buffer.extend(data)
        while True:
            if self.spec:
                length,crc,sequence=self.spec
                if len(self.buffer)<length+len(FOOTER):return
                jpeg=bytes(self.buffer[:length]);footer=bytes(self.buffer[length:length+len(FOOTER)])
                del self.buffer[:length+len(FOOTER)];self.spec=None
                if footer!=FOOTER:raise RuntimeError('Pico video framing failed. Disconnect and reconnect the desk Pico.')
                if zlib.crc32(jpeg)!=crc or not jpeg.startswith(b'\xff\xd8') or not jpeg.endswith(b'\xff\xd9'):
                    self.reject();continue
                self.publish(jpeg,sequence,f'{crc:08X}')
                continue
            index=self.buffer.find(b'\n')
            if index<0:
                if len(self.buffer)>4096:raise RuntimeError('Oversized Pico text reply. Reconnect the desk Pico.')
                return
            raw=bytes(self.buffer[:index]).rstrip(b'\r');del self.buffer[:index+1]
            if raw.startswith(b'VIDEO_FRAME'):
                match=FRAME_HEADER.fullmatch(raw)
                if not match:raise RuntimeError('Invalid Pico video header. Reconnect the desk Pico.')
                length,crc,sequence=match.groups();length=int(length)
                if not 4<=length<=32768:raise RuntimeError('Oversized Pico video frame. Reconnect the desk Pico.')
                self.spec=(length,int(crc,16),int(sequence))
            elif raw:
                if len(raw)>4096:raise RuntimeError('Oversized Pico text reply. Reconnect the desk Pico.')
                self.lines.append(raw.decode('ascii','strict'))


class RadioCamera:
    def __init__(self,bridge):
        self.bridge=bridge;self.condition=threading.Condition();self.enabled=False
        self.jpeg=None;self.generation=0;self.times=deque(maxlen=120);self.received=None
        self.value={'connected':False,'port':'PICO_WIFI','sensor':'XIAO ESP32-S3',
                    'error':None,'sequence':0,'source_sequence':0,'captured_at':None,
                    'transport':'WIFI_VIA_PICO','width':320,'height':240,'corrupt_frames':0}

    def state(self):
        with self.condition:
            now=time.monotonic();age=(now-self.received)*1000 if self.received is not None else None
            recent=[t for t in self.times if now-t<2]
            fps=(len(recent)-1)/(recent[-1]-recent[0]) if len(recent)>1 and recent[-1]>recent[0] else 0
            return dict(self.value,streaming=bool(self.enabled and age is not None and age<2000),
                        fps=round(fps,1),frame_age_ms=round(age) if age is not None else None,generation=self.generation)

    def connect(self,port):
        if port!='PICO_WIFI':raise ValueError('Choose the XIAO camera over Pico Wi-Fi.')
        if not self.bridge.connected or not self.bridge.identity:
            raise RuntimeError('Connect the desk Pico first, then start the wireless camera.')
        with self.condition:
            if self.enabled:return
            self.generation+=1;self.enabled=True;self.jpeg=None;self.times.clear();self.received=None
            self.value.update(connected=True,error=None,sequence=0,source_sequence=0,captured_at=None,corrupt_frames=0)
        try:self.bridge.camera_command('VIDEO ON')
        except RuntimeError:
            self.link_down();raise

    def disconnect(self):
        with self.condition:
            was_enabled=self.enabled;self.enabled=False;self.jpeg=None;self.received=None;self.times.clear()
            self.value.update(connected=False,error=None,captured_at=None);self.condition.notify_all()
        if was_enabled and self.bridge.connected and self.bridge.identity:self.bridge.camera_command('VIDEO OFF')

    def publish(self,jpeg,sequence,crc):
        with self.condition:
            if not self.enabled:return
            now=time.monotonic();self.jpeg=jpeg;self.received=now;self.times.append(now)
            self.value.update(sequence=self.value['sequence']+1,source_sequence=sequence,
                              captured_at=time.time(),bytes=len(jpeg),crc32=crc,error=None)
            self.condition.notify_all()

    def reject(self):
        with self.condition:self.value['corrupt_frames']+=1

    def link_down(self):
        with self.condition:
            self.enabled=False;self.value.update(connected=False,error='Desk Pico disconnected. Reconnect it to resume wireless video.')
            self.condition.notify_all()

    def wait_frame(self,after,generation,timeout=5):
        with self.condition:
            self.condition.wait_for(lambda:self.value['sequence']>after or not self.enabled or self.generation!=generation,timeout)
            if not self.enabled or self.generation!=generation or self.value['sequence']<=after:return None
            if self.received is None or time.monotonic()-self.received>2:return None
            return self.jpeg,dict(self.value)

    def image(self):
        with self.condition:return self.jpeg if self.enabled else None
