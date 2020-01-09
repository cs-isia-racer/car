import asyncio

import responder

MIN_STEERING, MAX_STEERING = -45, 45
MIN_THROTTLE, MAX_THROTTLE = 0, 1


def init_pwm():
    import wiringpi

    wiringpi.wiringPiSetupGpio()
    wiringpi.pinMode(18, wiringpi.GPIO.PWM_OUTPUT)
    wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)

    wiringpi.pwmSetClock(192)
    wiringpi.pwmSetRange(2000)


def compute_servo_value(steer):
    ratio = (steer - MIN_STEERING) / (MAX_STEERING - MIN_STEERING)
    # TODO: figure out correct values for the servo (50 to 200)
    return int(50 + (150 * ratio))


class Car:
    def __init__(self):
        # Steering goes from -90 to 90
        self.steering = 0
        self.throttle = 0
        self.capturing = AtomicBool(False)
        try:
            init_pwm()
        except Exception as err:
            print(f"Could not find PWM module: {err}")

    def update_steering(self, delta):
        self.steering = max(MIN_STEERING, min(self.steering + delta, MAX_STEERING))
        # TODO PWM write

        try:
            wiringpi.pwmWrite(18, compute_servo_value(self.steering))
        except Exception as err:
            # Ignore error
            pass

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

    @api.route("/capture/start")
    async def capture_start(req, resp):
        # TODO
        await car.capturing.set(True)
        resp.media = {"value": True}

    @api.route("/capture/stop")
    async def capture_stop(req, resp):
        # TODO
        await car.capturing.set(False)
        resp.media = {"value": False}

    api.run()


if __name__ == '__main__':
    run_api(Car())
