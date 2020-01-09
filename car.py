import responder

MAX_STEERING = 90
MIN_STEERING = -90

class Car:
    def __init__(self):
        self.api = responder.API()
        # Steering goes from -90 to 90
        self.steering = 0

    def update_steering(self, delta):
        self.steering = max(MIN_STEERING, min(self.steering + delta, MAX_STEERING))

    def run(self):
        @self.api.route("/steer/{delta}")
        async def steer(req, resp, *, delta):
            self.update_steering(int(delta))
            resp.text = f'Set steering to: {self.steering}'

        @self.api.route("/capture")
        async def steer(req, resp):
            # TODO
            resp.text = f'Starting capture'

        @self.api.route("/stop_capture")
        async def steer(req, resp):
            # TODO
            resp.text = f'Stopping capture'

        self.api.run()

if __name__ == '__main__':
    Car().run()
