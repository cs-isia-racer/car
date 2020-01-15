import argparse
import asyncio
import io
import time
from pathlib import Path

import responder

MIN_STEERING, MAX_STEERING = -90, 90
MIN_THROTTLE, MAX_THROTTLE = 0, 1

class Car:
    def __init__(self, mock=False, output=None):
        # Steering goes from -90 to 90
        self.steering = 0
        self.throttle = 0
        self.capturing = AtomicBool(False)
        self.output = Path(output or "out")
        if mock:
            from camera_mock import PiCamera
        else:
            from picamera import PiCamera
        self.camera = PiCamera(resolution=(224, 224), framerate=30)

    def update_steering(self, delta):
        self.steering = max(MIN_STEERING, min(self.steering + delta, MAX_STEERING))
        # TODO PWM write

    def set_throttle(self, throttle):
        self.throttle = max(MIN_THROTTLE, min(throttle, MAX_THROTTLE))
        # TODO PWM write


class AtomicBool:
    def __init__(self, value):
        self.value = value
        self.lock = asyncio.Lock()

    async def set(self, new):
        async with self.lock:
            self.value = new

    async def get(self):
        async with self.lock:
            res = self.value

        return res


def run_api(car, mock=False):
    api = responder.API()

    @api.route("/throttle/{value}")
    async def throttle(req, resp, *, value):
        car.set_throttle(int(value))
        resp.media = {"value": car.throttle}

    @api.route("/steer/{delta}")
    async def steer(req, resp, *, delta):
        car.update_steering(int(delta))
        resp.media = {"value": car.steering}

    @api.route("/capture")
    async def capture_get(req, resp):
        resp.media = {"value": await car.capturing.get()}

    async def capture():
        print("Starting capture")
        stream = io.BytesIO()
        for i, _ in enumerate(car.camera.capture_continuous(stream, format="jpeg", use_video_port=True)):
            await asyncio.sleep(1 / 60)
            if not await car.capturing.get():
                break
            stream.truncate()
            stream.seek(0)
            car.output.mkdir(parents=True, exist_ok=True)
            output_file = car.output / f"test_{i}"
            with open(output_file.as_posix(), "wb+") as f:
                print(f"saving file test_{i}")
                f.write(stream.getvalue())
        print("Stopping capture")

    @api.route("/capture/start")
    async def capture_start(req, resp):
        loop = asyncio.get_event_loop()
        await car.capturing.set(True)
        loop.create_task(capture())
        resp.media = {"value": True}

    @api.route("/capture/stop")
    async def capture_stop(req, resp):
        await car.capturing.set(False)
        resp.media = {"value": False}

    api.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--output", "-o", type=str)
    args = parser.parse_args()
    car = Car(mock=args.mock, output=args.output)
    car.camera.start_preview()
    time.sleep(5)
    run_api(car)
