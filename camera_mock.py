import time
import itertools
from pathlib import Path

class PiCamera:

    def __init__(self, resolution=(224, 224), framerate=30):
        self.resolution = resolution
        self.framerate = framerate

    def start_preview(self):
        pass

    def capture_continuous(self, output, format=None, use_video_port=False):
        mock_dir = Path(self.mock_dir).expanduser()

        images = ["fake image"]
        if mock_dir.exists() and mock_dir.is_dir():
            images_paths = mock_dir.glob("*.jpg")

            if images_paths:
                images = [
                    open(path, "rb").read()
                    for path in sorted(images_paths, key=lambda x: int(x.name.split('_')[1]))
                ]

        for raw in itertools.cycle(images):
            time.sleep(1 / self.framerate)
            output.write(raw)
            yield output
