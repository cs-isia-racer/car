import json
import base64

import numpy as np
import cv2
import websocket
import requests


class AbstractClient:
    def __init__(self, host, rate):
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
        msg = json.loads(message)
        if "state" not in msg:
            return

        self._counter += 1
        if self._counter % self.every == 0:
            raw_image = base64.b64decode(msg["state"]["image"])
            image = cv2.imdecode(np.frombuffer(raw_image, np.uint8), -1)

            try:
                angle, img = self.process(image)
            except Exception as err:
                print(f"Error: {err}")
                angle, img = 0, None

            payload = {"command": {"steering": angle}}

            if img is not None:
                payload["data"] = {"image": img}

            self.ws.send(json.dumps(payload))
            print(f"Sent angle command: {angle}")

    def start(self):
        self.session.get(f"http://{self.host}/stream/start")
        self.ws = websocket.WebSocketApp(
            f"ws://{self.host}/ws",
            on_message=self.on_message,
            on_error=lambda ws, msg: print("error", msg),
            on_close=lambda ws: print("closed"),
        )

        self.ws.run_forever()


    def cv2encode(self, img):
        return base64.b64encode(cv2.imencode(".JPEG", img)[1]).decode()

    @classmethod
    def bootstrap(cls, rate=0.05, **kwargs):
        import sys

        cls(sys.argv[1], rate=rate, **kwargs).start()
