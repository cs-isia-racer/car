import cv2
import numpy as np
import math

from clients.abstract_client import AbstractClient


class AngleEstimator:
    def __init__(
        self,
        kernel_size=7, # Kernel size for the gaussian blur
        low_t=30,      # Low threhsold for the canny
        high_t=90,    # High threshold for the canny
        hough_t=40,    # Minimum number of votes (intersection in Hough grid cell)
        min_line_length=20, #  minimum number of pixels making up a line
        max_line_gap=10,    # maximum gap in pixels between connectable line segments
        offset=50, # offset for the image
        angle_limit=70 # max angle acceptable for processing in degrees
    ):
        self.kernel_size = kernel_size
        self.low_t = low_t
        self.high_t = high_t
        self.hough_t = hough_t
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.offset = offset
        self.angle_limit = angle_limit
        self._last_angle = 0


    def predict(self, X):
        return np.array([self.predict_one(x) for x in X])


    def predict_one(self, img, verbose=False):
        lines = self._lines(img)
        if lines is None:
            if verbose:
                print("No lines found")
            return 0

        return self._angle(lines, verbose=verbose)

    def _preprocess(self, img):
        img = img[self.offset:]

        img = cv2.GaussianBlur(img, (self.kernel_size, self.kernel_size), 0)

        img = cv2.Canny(img, self.low_t, self.high_t)

        return img

    def _lines(self, img):
        edges = self._preprocess(img)

        rho = 1  # distance resolution in pixels of the Hough grid
        theta = np.pi / 180  # angular resolution in radians of the Hough grid

        # Run Hough on edge detected image
        # Output "lines" is an array containing endpoints of detected line segments
        return cv2.HoughLinesP(edges, rho, theta, self.hough_t, np.array([]),
                            self.min_line_length, self.max_line_gap)

    def _line_angle(self, x1, y1, x2, y2, verbose=False):
        angle = None
        if y2 == y1:
            angle = math.pi/2 if x2 > x1 else -math.pi/2
        else:
            angle = math.atan((x2 - x1) / (y2 - y1))

        if verbose:
            print(f"Angle found: {-angle} rad, {-angle*180/math.pi} degrees")

        # Only keep realistic angles
        if abs(180/math.pi * angle) > self.angle_limit:
            return None

        return angle

    def _angle(self, lines, normalize=True, verbose=False):
        # Angle between -30 and 30 (-1 and 1)

        angles = []
        lengths = []
        if verbose:
            print("Lines: ", lines)

        for line in lines:
            for x1, y1, x2, y2 in line:
                angle = self._line_angle(x1, y1, x2, y2, verbose=verbose)
                if angle:
                    angles.append(angle)
                    lengths.append(max(abs(x2-x1), abs(y2-y1)))

        if not angles:
            if verbose:
                print("No valid angles found")
            return 0

        angles = np.array(angles)
        lengths = np.array(lengths)

        weighted_mean_angle = np.sum(angles * lengths) / np.sum(lengths)

        a = -180/math.pi * np.mean(weighted_mean_angle)

        if normalize:
            a = min(30, max(-30, a)) / 30

        return a

    def _draw_lines(self, img, lines):
        line_image = np.zeros_like(img)

        for line in lines:
            for x1,y1,x2,y2 in line:
                color = (255, 0, 0) if self._line_angle(x1, y1, x2, y2) is None else (0, 255, 0)
                cv2.line(line_image,(x1,y1+self.offset),(x2,y2+self.offset),color,5)

        dy = 30
        dx = int(dy * math.tan(self._angle(lines)))
        x = img.shape[1] //2
        y = img.shape[0] -1

        cv2.arrowedLine(line_image, (x, y), (x+dx, y-dy), (255, 255, 255), 5)

        # Draw the lines on the  image
        lines_edges = cv2.addWeighted(img, 0.8, line_image, 1, 0)

        return lines_edges

    def predict_and_draw(self, img):
        lines = self._lines(img)
        if lines is None:
            return self._last_angle

        angle = self._angle(lines)

        self._last_angle = angle

        return angle, self._draw_lines(img, lines)


class HoughClient(AbstractClient):
    def __init__(self, host, rate, **kwargs):
        super(HoughClient, self).__init__(host, rate)
        self.estimator = AngleEstimator(**kwargs)

    def process(self, image):
        ang, draw = self.estimator.predict_and_draw(image)
        return ang, self.cv2encode(draw)


if __name__ == "__main__":
    HoughClient.bootstrap(0.2)
