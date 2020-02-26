import argparse
import asyncio
import base64
import io
import time
import uuid
from pathlib import Path

import responder

MIN_STEERING, MAX_STEERING = -1, 1
MIN_THROTTLE, MAX_THROTTLE = -1, 1


class Car:
    STEERING_PIN = 13
    THROTTLE_PIN = 18

    def __init__(self, mock_cam_dir, mock_pwm):
        # Steering goes from -90 to 90
        self.steering = Atomic(0)
        self.throttle = Atomic(0)
        self.capturing = Atomic(False)

        if mock_cam_dir is not None:
            from mocks.camera_mock import PiCamera
        else:
            from picamera import PiCamera
        if mock_pwm:
            import mocks.wiringpi_mock as wiringpi
        else:
            import wiringpi

        self.camera = PiCamera(resolution=(1000, 1000), framerate=60)
        if mock_cam_dir is not None:
            self.camera.mock_dir = mock_cam_dir

        for pin in [self.STEERING_PIN, self.THROTTLE_PIN]:
            wiringpi.wiringPiSetupGpio()
            wiringpi.pinMode(pin, wiringpi.GPIO.PWM_OUTPUT)
            wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)
            wiringpi.pwmSetClock(192)
            wiringpi.pwmSetRange(2000)

        self.pwmWrite = wiringpi.pwmWrite

    async def set_steering(self, steering):
        await self.steering.set(max(MIN_STEERING, min(steering, MAX_STEERING)))
        self.pwmWrite(self.STEERING_PIN, int(135 + 30 * steering))
        return steering


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


class WSRegistry:
    def __init__(self):
        self.clients = {}
        self.lock = asyncio.Lock()

    async def add(self, ws):
        async with self.lock:
            ws.id = uuid.uuid4()
            self.clients[ws.id] = ws
            print(f"New client connected ! id: {ws.id}")

    async def remove(self, id):
        async with self.lock:
            if id in self.clients:
                self.clients.pop(id)
                print(f"client with id: {id} disconnected")

    async def broadcast(self, message, sender=None):
        async with self.lock:
            for id, client in self.clients.items():
                if sender is None or id != sender:
                    await client.send_json(message)


async def safe_ws_loop(ws, fn):
    try:
        while True:
            await fn()
    except Exception as err:
        print(f"closing connection after error: {err}")
    try:
        await ws.close()
    except Exception:
        pass


def run_api(car):
    api = responder.API()
    capture_stream = AtomicStream(io.BytesIO())

    registry = WSRegistry()

    async def run_stream():
        stream = io.BytesIO()

        new = time.time_ns()
        rates = []
        for _ in car.camera.capture_continuous(
            stream, format="jpeg", use_video_port=True
        ):
            start = new
            #   await asyncio.sleep(1 / 60)
            stream.truncate()
            stream.seek(0)

            image = stream.getvalue()
            throttle, steering = await asyncio.gather(
                car.throttle.get(), car.steering.get()
            )

            await registry.broadcast(
                {
                    "state": {
                        "throttle": throttle,
                        "steering": steering,
                        "image": base64.b64encode(image).decode(),
                    }
                }
            )

            if await car.capturing.get():
                await capture_stream.write(image)

            new = time.time_ns()
            rates.append(1000000000 / (new - start))

            if len(rates) > 20:
                print("Average framerate:", sum(rates) / len(rates))
                rates = []

        print("Stopping stream")

    @api.on_event("startup")
    def start_stream():
        loop = asyncio.get_event_loop()
        loop.create_task(run_stream())
        print("Started video stream")

    @api.route("/ws", websocket=True)
    async def websocket(ws):
        await ws.accept()

        await registry.add(ws)

        async def process_messages():
            msg = await ws.receive_json()
            if "command" in msg:
                command = msg["command"]
                print(f"received command: {command}")
                await car.set_steering(command.get("steering", MIN_STEERING))
            if "data" in msg:
                print("received image from model, it will be broadcasted")
                await registry.broadcast(msg, ws.id)

        async def receive_data():
            await safe_ws_loop(ws, process_messages)
            await registry.remove(ws.id)

        await receive_data()

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
            throttle, steering = await asyncio.gather(
                car.throttle.get(), car.steering.get()
            )
            output_file = out / f"pic_{i}_{float(steering)}_{float(throttle)}.jpg"
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
        out = Path(out or f"out.{time.time()}")
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
    parser.add_argument(
        "--mock-cam-dir",
        default=None,
        type=str,
        help="Directory that contains images to return to mock the camera",
    )
    parser.add_argument("--mock-pwm", action="store_true")
    args = parser.parse_args()
    car = Car(args.mock_cam_dir, args.mock_pwm)
    car.camera.start_preview()
    if not args.mock_cam_dir:
        time.sleep(5)
    run_api(car)
