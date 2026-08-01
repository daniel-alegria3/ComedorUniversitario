#!/usr/bin/env python3

import sys
import cv2
import numpy as np

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <image>")
    sys.exit(1)

image = cv2.imread(sys.argv[1])
if image is None:
    print(f"Could not open '{sys.argv[1]}'")
    sys.exit(1)

points = []
selected = -1
warped = None


def order_points(pts):
    pts = np.asarray(pts, dtype=np.float32)

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]      # top-left
    ordered[1] = pts[np.argmin(diff)]   # top-right
    ordered[2] = pts[np.argmax(s)]      # bottom-right
    ordered[3] = pts[np.argmax(diff)]   # bottom-left

    return ordered


def compute_warp():
    global warped

    src = order_points(points)

    width = int(max(
        np.linalg.norm(src[2] - src[3]),
        np.linalg.norm(src[1] - src[0]),
    ))

    height = int(max(
        np.linalg.norm(src[1] - src[2]),
        np.linalg.norm(src[0] - src[3]),
    ))

    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src, dst)

    warped = cv2.warpPerspective(
        image,
        M,
        (width, height),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )


def mouse(event, x, y, flags, param):
    global selected

    if event == cv2.EVENT_LBUTTONDOWN:

        # Add points until there are four.
        if len(points) < 4:
            points.append([x, y])

        else:
            # Select the closest point.
            for i, p in enumerate(points):
                if np.linalg.norm(np.array(p) - np.array([x, y])) < 15:
                    selected = i
                    break

    elif event == cv2.EVENT_MOUSEMOVE:

        if selected != -1:
            points[selected] = [x, y]
            compute_warp()

    elif event == cv2.EVENT_LBUTTONUP:
        selected = -1


cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Image", mouse)

while True:

    display = image.copy()

    # Draw points
    for p in points:
        cv2.circle(display, tuple(p), 6, (0, 255, 0), -1)

    # Draw polygon + update warp
    if len(points) == 4:
        ordered = order_points(points)

        for i in range(4):
            cv2.line(
                display,
                tuple(ordered[i].astype(int)),
                tuple(ordered[(i + 1) % 4].astype(int)),
                (0, 255, 0),
                2,
            )

        if warped is None:
            compute_warp()

        cv2.imshow("Warped", warped)

    cv2.imshow("Image", display)

    key = cv2.waitKey(20) & 0xFF

    if key == ord("q"):
        if warped is not None:
            cv2.imwrite("output.png", warped)
            print("Saved as output.png")
        break

cv2.destroyAllWindows()
