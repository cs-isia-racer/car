from clients.abstract_client import AbstractClient


last = 1


class DummyClient(AbstractClient):
    def process(self, image):
        global last
        last *= -1
        return last, None


if __name__ == "__main__":
    DummyClient.bootstrap(0.2)
