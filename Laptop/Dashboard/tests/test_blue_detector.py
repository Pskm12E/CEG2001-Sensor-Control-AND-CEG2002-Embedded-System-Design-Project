"""Image and stream tests; synthetic fixtures never open a serial port."""
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blue_detector import BlueSquare, DetectionVideo, cv2, np
from camera_radio import RadioCamera


def fixture(kind="square", colour=(200, 90, 30), offset=0):
    image = np.full((240, 320, 3), 225, np.uint8)
    if kind == "square":
        cv2.rectangle(image, (100+offset, 70), (150+offset, 120), colour, -1)
    elif kind == "rectangle":
        cv2.rectangle(image, (70, 70), (200, 95), colour, -1)
    elif kind == "circle":
        cv2.circle(image, (150, 100), 30, colour, -1)
    elif kind == "tiny":
        cv2.rectangle(image, (100, 70), (104, 74), colour, -1)
    elif kind == "rotated":
        points = cv2.boxPoints(((150, 100), (48, 48), 35)).astype(np.int32)
        cv2.fillConvexPoly(image, points, colour)
    ok, result = cv2.imencode('.jpg', image)
    assert ok
    return result.tobytes()


@unittest.skipIf(cv2 is None, "Install dashboard OpenCV requirements")
class ImageTests(unittest.TestCase):
    def test_confirm_then_clear_when_target_removed(self):
        detector = BlueSquare()
        for index in range(3):
            jpeg, result = detector.process(fixture(), index*0.07)
            self.assertEqual(result['detected'], index == 2)
        self.assertEqual(result['status'], 'DETECTED')
        self.assertAlmostEqual(result['centre'][0], 125, delta=3)
        self.assertIsNotNone(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR))
        _, result = detector.process(fixture('empty'), 0.25)
        self.assertFalse(result['detected'])
        self.assertIsNone(result['box'])

    def test_nonblue_shapes_and_noise_are_rejected(self):
        for kind, colour in [('circle',(200,90,30)), ('rectangle',(200,90,30)),
                             ('tiny',(200,90,30)), ('square',(20,30,210)), ('empty',(0,0,0))]:
            with self.subTest(kind=kind, colour=colour):
                _, result = BlueSquare().process(fixture(kind, colour))
                self.assertIsNone(result['box'])

    def test_rotation_supported_and_target_jump_restarts_confirmation(self):
        detector = BlueSquare()
        for index in range(3):
            _, result = detector.process(fixture('rotated'), index*0.05)
        self.assertTrue(result['detected'])
        detector = BlueSquare()
        detector.process(fixture(), 0)
        detector.process(fixture(), 0.05)
        _, result = detector.process(fixture(offset=110), 0.1)
        self.assertEqual(result['streak'], 1)
        self.assertFalse(result['detected'])

    def test_gap_and_invalid_jpeg_reset_confirmation(self):
        detector = BlueSquare()
        detector.process(fixture(), 0)
        detector.process(fixture(), 0.05)
        _, result = detector.process(fixture(), 1)
        self.assertEqual(result['streak'], 1)
        with self.assertRaises(ValueError):
            detector.process(b'invalid jpeg')
        _, result = detector.process(fixture(), 1.1)
        self.assertEqual(result['streak'], 1)


@unittest.skipIf(cv2 is None, "Install dashboard OpenCV requirements")
class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.camera = RadioCamera(SimpleNamespace())
        self.camera.enabled = True
        self.camera.value['connected'] = True
        self.camera.generation = 1
        self.detector = DetectionVideo(self.camera)

    def tearDown(self):
        self.detector.stop()

    def publish(self, source_sequence, kind='square'):
        jpeg = fixture(kind)
        self.camera.publish(jpeg, source_sequence, f'{zlib.crc32(jpeg):08X}')

    def wait_processed(self, after):
        frame = self.detector.wait_frame(after, self.detector.generation, timeout=1)
        self.assertIsNotNone(frame)
        return frame[1]['sequence']

    def test_distinct_frames_confirm_and_stale_result_disappears(self):
        self.detector.start()
        after = 0
        for source in range(1, 4):
            self.publish(source)
            after = self.wait_processed(after)
        self.assertTrue(self.detector.state()['detected'])
        self.detector.received = time.monotonic()-1
        state = self.detector.state()
        self.assertFalse(state['fresh'])
        self.assertFalse(state['detected'])
        self.assertIsNone(state['box'])
        self.assertFalse(state['actuator_control'])

    def test_duplicate_camera_sequence_cannot_confirm_target(self):
        self.detector.start()
        self.publish(10)
        self.wait_processed(0)
        for _ in range(3):
            self.publish(10)
            time.sleep(0.03)
        self.assertEqual(self.detector.state()['sequence'], 1)
        self.assertFalse(self.detector.state()['detected'])
        self.publish(11)
        after = self.wait_processed(1)
        self.publish(12)
        self.wait_processed(after)
        self.assertTrue(self.detector.state()['detected'])

    def test_stop_and_source_restart_clear_old_detection(self):
        self.detector.start()
        after = 0
        for source in range(1, 4):
            self.publish(source)
            after = self.wait_processed(after)
        self.camera.generation += 1
        self.assertFalse(self.detector.state()['detected'])
        self.publish(4)
        self.wait_processed(after)
        self.assertFalse(self.detector.state()['detected'])
        self.detector.stop()
        self.assertEqual(self.detector.state()['status'], 'OFF')
        self.assertIsNone(self.detector.wait_frame(0, self.detector.generation, timeout=0))
        self.assertTrue(self.camera.state()['connected'])

    def test_start_requires_camera(self):
        self.camera.value['connected'] = False
        with self.assertRaises(RuntimeError):
            self.detector.start()

    def test_equal_clock_ticks_do_not_break_state(self):
        tick = time.monotonic()
        self.detector.times.extend([tick, tick, tick])
        self.assertEqual(self.detector.state()['fps'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
