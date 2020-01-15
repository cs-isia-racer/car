import argparse
import asyncio
import io
import time
from pathlib import Path

import responder

MIN_STEERING, MAX_STEERING = -90, 90
MIN_THROTTLE, MAX_THROTTLE = 0, 1

class Car:
    STEERING_PIN = 18

    def __init__(self, mock=False):
        # Steering goes from -90 to 90
        self.steering = 0
        self.throttle = 0
        self.capturing = AtomicBool(False)
        if mock:
            from camera_mock import PiCamera
            import wiringpi_mock as wiringpi
        else:
            from picamera import PiCamera
            import wiringpi
        self.camera = PiCamera(resolution=(224, 224), framerate=30)
        wiringpi.wiringPiSetupGpio()
        wiringpi.pinMode(self.STEERING_PIN, wiringpi.GPIO.PWM_OUTPUT)
        wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
        wiringpi.pwmSetClock(192)
        wiringpi.pwmSetRange(2000)
        self.pwmWrite = wiringpi.pwmWrite

    def update_steering(self, delta):
        self.steering = max(MIN_STEERING, min(self.steering + delta, MAX_STEERING))
        self.pwmWrite(self.STEERING_PIN, self.steering)

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


def run_api(car):
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

    async def capture(out):
        print("Starting capture")
        stream = io.BytesIO()
        for i, _ in enumerate(car.camera.capture_continuous(stream, format="jpeg", use_video_port=True)):
            await asyncio.sleep(1 / 60)
            if not await car.capturing.get():
                break
            stream.truncate()
            stream.seek(0)
            out.mkdir(parents=True, exist_ok=True)
            output_file = out / f"test_{i}_{car.steering}_{car.throttle}.jpg"
            posix_file_str = output_file.as_posix()
            with open(posix_file_str, "wb+") as f:
                print(f"saving file {posix_file_str}")
                f.write(stream.getvalue())
        print("Stopping capture")

    @api.route("/capture/start")
    async def capture_start(req, resp):
        if await car.capturing.get():
            resp.status_code = api.status_codes.HTTP_400
            resp.media = {"error": "already capturing"}
            return
        out = req.params.get("out")
        out = Path(out or "out")
        loop = asyncio.get_event_loop()
        await car.capturing.set(True)
        loop.create_task(capture(out))
        resp.media = {"value": True}

    @api.route("/capture/stop")
    async def capture_stop(req, resp):
        if not await car.capturing.get():
            resp.status_code = api.status_codes.HTTP_400
            resp.media = {"error": "no capture to stop"}
            return
        await car.capturing.set(False)
        resp.media = {"value": False}

    api.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    car = Car(mock=args.mock)
    car.camera.start_preview()
    time.sleep(5)
    run_api(car)
