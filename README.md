# car

The goal of this project is to build a small "framework" around autonomous card driving that would allow it's users to record datasets and load models.

## Setup

First download the dependencies: `pip3 install -r requirements.txt`

Then start the server on a raspberry PI: `PORT=8080 PYTHONPATH=. python3 car.py`

### Mocking the camera and the PWM outputs

If you want to run a mocked server you can also do that by running:

`PYTHONPATH=. python3 car.py --mock-pwm --mock-cam-dir <IMG_DIR>`

Where IMG_DIR is a directory of images produced by the capture.

### Running a model

To run a model you can use one of the clients provided in the `clients` directory like [the hough one](./clients/hough_client.py).

You can also build your own client by implementing the [abstract_client class](./clients/abstract_client.py)

The only method needed is the `process` method that takes an image in opencv2 format and returns a tuple `(angle, annotated_image)` where `angle` is in [-1, 1] and `annotated_image` can be None

## Internals

TODO
