import cv2
import numpy as np
import math

from clients.abstract_client import AbstractClient


# https://stackoverflow.com/questions/45322630/how-to-detect-lines-in-opencv
def compute_lines(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    kernel_size = 5
    blur_gray = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)

    low_threshold = 50
    high_threshold = 150
    edges = cv2.Canny(blur_gray, low_threshold, high_threshold)

    rho = 1  # distance resolution in pixels of the Hough grid
    theta = np.pi / 180  # angular resolution in radians of the Hough grid
    threshold = 60  # minimum number of votes (intersections in Hough grid cell)
    min_line_length = 70  # minimum number of pixels making up a line
    max_line_gap = 10  # maximum gap in pixels between connectable line segments

    # Run Hough on edge detected image
    # Output "lines" is an array containing endpoints of detected line segments
    return cv2.HoughLinesP(
        edges, rho, theta, threshold, np.array([]), min_line_length, max_line_gap
    )


def compute_angle(lines):
    # Angle between -30 and 30 (-1 and 1)
    angles = []
    for line in lines:
        for x1, y1, x2, y2 in line:
            angles.append(math.atan((x2 - x1) / (y2 - y1)))

    a = -180 / math.pi * np.mean(angles)

    if a < -30:
        a = -30
    elif a > 30:
        a = 30

    return a / 30


class HoughClient(AbstractClient):
    def process(self, image):
        try:
            image = image[122:, :]
            lines = compute_lines(image)

            line_image = np.copy(image) * 0  # creating a blank to draw lines on
            for line in lines:
                for x1, y1, x2, y2 in line:
                    cv2.line(line_image, (x1, y1), (x2, y2), (255, 0, 0), 5)

            lines_edges = cv2.addWeighted(image, 0.8, line_image, 1, 0)

            return compute_angle(lines), self.cv2encode(lines_edges)
        except:
            return 0, None


if __name__ == "__main__":
    HoughClient.bootstrap(0.2)
