import websocket
import requests
import json
import base64


class AbstractClient:
    def __init__(self, host, rate=0.05):
        if rate is None or rate == 0:
            self.every = 1
        else:
            self.every = 1 / rate

        self._counter = 0
        self.host = host
        self.session = requests.Session()

    def process(self, image):
        raise NotImplementedError

    def on_message(self, message):
        self._counter += 1
        if self._counter % self.every == 0:
            image = base64.b64decode(json.loads(message)['image'])
            angle = self.process(image)

            self.session.get(f"http://{self.host}/steer/set/{angle}")
            print(f"Sent angle command: {angle}")

    def start(self):
        self.session.get(f"http://{self.host}/stream/start")
        websocket.enableTrace(True)
        ws = websocket.WebSocketApp(
            f'ws://{self.host}/ws',
            on_message=self.on_message,
            on_error=lambda ws, msg: print("error", msg),
            on_close=lambda ws: print("closed"),
        )

        ws.run_forever()
