import asyncio

import responder

MIN_STEERING, MAX_STEERING = -90, 90
MIN_THROTTLE, MAX_THROTTLE = 0, 1

class Car:
    def __init__(self):
        self.api = responder.API()
        # Steering goes from -90 to 90
        self.steering = 0
        self.throttle = 0
        self.capturing = AtomicBool(False)

    def update_steering(self, delta):
        self.steering = max(MIN_STEERING, min(self.steering + delta, MAX_STEERING))
        # TODO PWM write

    def set_throttle(self, throttle):
        self.throttle = max(MIN_THROTTLE, min(throttle, MAX_THROTTLE))
        # TODO PWM write

    def run(self):
        @self.api.route("/throttle/{value}")
        async def steer(req, resp, *, value):
            self.set_throttle(int(value))
            resp.text = f'Set steering to: {self.throttle}'

        @self.api.route("/steer/{delta}")
        async def steer(req, resp, *, delta):
            self.update_steering(int(delta))
            resp.text = f'Set steering to: {self.steering}'

        @self.api.route("/capture")
        async def steer(req, resp):
            # TODO
            await self.capturing.set(True)
            resp.text = f'Starting capture'

        @self.api.route("/stop_capture")
        async def steer(req, resp):
            # TODO
            await self.capturing.set(False)
            resp.text = f'Stopping capture'

        self.api.run()

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

if __name__ == '__main__':
    Car().run()
