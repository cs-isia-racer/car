import time

class PiCamera:

    def __init__(self, resolution=(224, 224), framerate=30):
        self.resolution = resolution
        self.framerate = framerate

    def start_preview(self):
        pass

    def capture_continuous(self, output, format=None, use_video_port=False):
        i = 0
        while True:
            time.sleep(1 / self.framerate)
            output.write(b"capture_id: %d" % i)
            yield output
            i += 1
