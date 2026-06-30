import asyncio
import logging
import os
from typing import Dict, Optional, Any

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from heiman.perception.collector import BaseCollector, CollectorConfig, CollectorType


logger = logging.getLogger(__name__)


class CameraAdapter:
    def __init__(self, camera_id: int = 0, fps: int = 10, motion_threshold: float = 10.0):
        self.camera_id = camera_id
        self.fps = fps
        self.motion_threshold = motion_threshold
        self.cap = None
        self._prev_frame = None
        self._running = False

    async def open(self) -> bool:
        if not HAS_OPENCV:
            logger.warning("OpenCV not installed, camera adapter disabled")
            return False

        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}")
                return False

            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            logger.info(f"Camera {self.camera_id} opened successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to open camera: {e}")
            return False

    async def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        self._running = False

    async def capture_frame(self) -> Optional[Dict[str, Any]]:
        if not self.cap or not self.cap.isOpened():
            return None

        try:
            ret, frame = self.cap.read()
            if not ret:
                return None

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            motion_detected = False
            if self._prev_frame is not None:
                frame_delta = cv2.absdiff(self._prev_frame, gray)
                thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    if cv2.contourArea(contour) > 500:
                        motion_detected = True
                        break

            self._prev_frame = gray

            return {
                "success": True,
                "motion_detected": motion_detected,
                "frame_width": frame.shape[1],
                "frame_height": frame.shape[0],
                "timestamp": asyncio.get_event_loop().time(),
            }
        except Exception as e:
            logger.error(f"Capture frame failed: {e}")
            return None

    async def capture_with_face_detection(self) -> Optional[Dict[str, Any]]:
        frame_data = await self.capture_frame()
        if not frame_data or not frame_data.get("success"):
            return frame_data

        try:
            import cv2
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

            ret, frame = self.cap.read()
            if not ret:
                return frame_data

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            frame_data.update({
                "face_detected": len(faces) > 0,
                "face_count": len(faces),
                "faces": [
                    {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                    for (x, y, w, h) in faces
                ],
            })
        except Exception as e:
            logger.warning(f"Face detection failed: {e}")

        return frame_data


class CameraCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._camera_adapter = None
        self._camera_id = config.config.get("camera_id", 0)
        self._enable_face_detection = config.config.get("enable_face_detection", False)

    async def start(self):
        await super().start()
        self._camera_adapter = CameraAdapter(camera_id=self._camera_id)
        success = await self._camera_adapter.open()

        if success:
            asyncio.create_task(self._collection_loop())
        else:
            logger.warning("Camera collector failed to start, falling back to mock data")
            asyncio.create_task(self._mock_loop())

    async def stop(self):
        await super().stop()
        if self._camera_adapter:
            await self._camera_adapter.close()

    async def _collection_loop(self):
        while self._running:
            if self._enable_face_detection:
                data = await self._camera_adapter.capture_with_face_detection()
            else:
                data = await self._camera_adapter.capture_frame()

            if data and self._callback:
                event_data = {
                    "type": "camera_event",
                    "location": self.config.config.get("location", "unknown"),
                    "motion_detected": data.get("motion_detected", False),
                    "face_detected": data.get("face_detected", False),
                    "face_count": data.get("face_count", 0),
                    "timestamp": data.get("timestamp", asyncio.get_event_loop().time()),
                    "confidence": 0.85 if data.get("motion_detected") else 0.0,
                }
                await self._callback(event_data)

            await asyncio.sleep(1.0 / self.config.interval)

    async def _mock_loop(self):
        while self._running:
            event_data = {
                "type": "camera_event",
                "location": self.config.config.get("location", "living_room"),
                "motion_detected": False,
                "face_detected": False,
                "face_count": 0,
                "timestamp": asyncio.get_event_loop().time(),
                "confidence": 0.7,
            }
            if self._callback:
                await self._callback(event_data)
            await asyncio.sleep(self.config.interval)