# Future insect detector weights

The planned YOLO model runs on the **laptop**, alongside the local Python
dashboard. A future trained checkpoint can live here as `pest_detector.pt`, or
an exported inference model as `pest_detector.onnx`. These are proposed paths,
not files supplied with the project. No YOLO weights have been trained or loaded.

The current practice detector is [Dashboard/blue_detector.py](../Dashboard/blue_detector.py): OpenCV HSV blue-colour
segmentation, quadrilateral/size filtering and three-frame confirmation. It
detects the blue square, not insects, and sends no robot-control commands.

For a future toy-insect model, train and evaluate on labelled examples of that
actual target and the real camera scenes. Replacing the detector does not change
the robot authority: detection reports must be checked by the main MSP430 before
the Uno or spray driver is commanded. Model inference on the XIAO would require
a separate conversion, firmware and memory/performance validation effort.
