import argparse
import asyncio
import base64
import io
import time
from pathlib import Path

import responder

MIN_STEERING, MAX_STEERING = -1, 1
MIN_THROTTLE, MAX_THROTTLE = -1, 1


class Car:
    STEERING_PIN = 13
    THROTTLE_PIN = 18

    def __init__(self, mock_cam=False, mock_pwm=False):
        # Steering goes from -90 to 90
        self.steering = Atomic(0)
        self.throttle = Atomic(0)
        self.capturing = Atomic(False)

        if mock_cam:
            from camera_mock import PiCamera
        else:
            from picamera import PiCamera
        if mock_pwm:
            import wiringpi_mock as wiringpi
        else:
            import wiringpi

        self.camera = PiCamera(resolution=(224, 224), framerate=30)

        for pin in [self.STEERING_PIN, self.THROTTLE_PIN]:
            wiringpi.wiringPiSetupGpio()
            wiringpi.pinMode(pin, wiringpi.GPIO.PWM_OUTPUT)
            wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
            wiringpi.pwmSetClock(192)
            wiringpi.pwmSetRange(2000)

        self.pwmWrite = wiringpi.pwmWrite

    async def update_steering(self, delta):
        # FIXME there could be race conditions here
        steering = await self.steering.get()
        return self.set_steering(steering + delta)

    async def set_steering(self, steering):
        await self.steering.set(max(MIN_STEERING, min(steering, MAX_STEERING)))
        self.pwmWrite(self.STEERING_PIN, int(135 + 30 * steering))
        return steering

    async def update_throttle(self, delta):
        # FIXME there could be race conditions here
        throttle = await self.throttle.get()
        await self.throttle.set(max(MIN_THROTTLE, min(throttle + delta, MAX_THROTTLE)))
        self.pwmWrite(self.THROTTLE_PIN, int(90 + 30 * throttle))
        return throttle


class Atomic:
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


class AtomicStream:
    def __init__(self, stream):
        self.stream = stream
        self.lock = asyncio.Lock()

    async def write(self, value):
        async with self.lock:
            self.stream.write(value)
            self.stream.truncate()
            self.stream.seek(0)

    async def read(self):
        async with self.lock:
            res = self.stream.getvalue()
        return res


def run_api(car):
    api = responder.API()
    dashboard_stream = AtomicStream(io.BytesIO())
    capture_stream = AtomicStream(io.BytesIO())

    async def run_stream():
        print("Starting stream")
        stream = io.BytesIO()
        for _ in car.camera.capture_continuous(
            stream, format="jpeg", use_video_port=True
        ):
            await asyncio.sleep(1 / 60)
            stream.truncate()
            stream.seek(0)
            value = stream.getvalue()
            await dashboard_stream.write(value)
            await capture_stream.write(value)
        print("Stopping stream")

    @api.route("/stream/start")
    async def stream_start(req, resp):
        loop = asyncio.get_event_loop()
        loop.create_task(run_stream())
        resp.media = {"value": True}

    @api.route("/ws", websocket=True)
    async def websocket(ws):
        await ws.accept()
        while True:
            await asyncio.sleep(1 / 60)
            throttle, steering, image = await asyncio.gather(
                car.throttle.get(), car.steering.get(), dashboard_stream.read(),
            )
            await ws.send_json(
                {
                    "throttle": throttle,
                    "steering": steering,
                    "image": base64.b64encode(image).decode(),
                }
            )
        await ws.close()

    @api.route("/throttle/{value}")
    async def throttle(req, resp, *, value):
        resp.media = {"value": await car.update_throttle(float(value))}

    @api.route("/steer/{delta}")
    async def steer(req, resp, *, delta):
        resp.media = {"value": await car.update_steering(float(delta))}

    @api.route("/steer/set/{steering}")
    async def steer(req, resp, *, steering):
        resp.media = {"value": await car.set_steering(float(steering))}

    @api.route("/capture")
    async def capture_get(req, resp):
        resp.media = {"value": await car.capturing.get()}

    async def capture(out):
        print("Starting capture")
        i = 0
        while True:
            await asyncio.sleep(1 / 60)
            value = await capture_stream.read()
            if not await car.capturing.get():
                break
            out.mkdir(parents=True, exist_ok=True)
            output_file = out / f"pic_{i}_{car.steering}_{car.throttle}.jpg"
            posix_file_str = output_file.as_posix()
            with open(posix_file_str, "wb+") as f:
                print(f"saving file {posix_file_str}")
                f.write(value)
            i += 1
        print("Stopping capture")

    @api.route("/capture/start")
    async def capture_start(req, resp):
        if await car.capturing.get():
            resp.status_code = api.status_codes.HTTP_400
            resp.media = {"error": "already capturing"}
            return
        out = req.params.get("out")
        out = Path(out or "out")
        if out.exists():
            resp.status_code = api.status_codes.HTTP_400
            resp.media = {"error": "can't start capture into existing folder"}
            return
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock-cam", action="store_true")
    parser.add_argument("--mock-pwm", action="store_true")
    args = parser.parse_args()
    car = Car(mock_cam=args.mock_cam, mock_pwm=args.mock_pwm)
    car.camera.start_preview()
    if not args.mock_cam:
        time.sleep(5)
    run_api(car)
