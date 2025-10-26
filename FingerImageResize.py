import math

import cv2
import mediapipe as mp
import time
import HandTrackingModule as htm

pTime = 0
cTime = 0
cap = cv2.VideoCapture(0)
detector = htm.handDetector();

fingerImg = cv2.imread("jack.jpg", cv2.IMREAD_COLOR)
if fingerImg is None:
    raise FileNotFoundError("jack.jpg not found (check path)")

# If image has alpha, drop it (we want 100% opacity over the ROI)
if fingerImg.ndim == 3 and fingerImg.shape[2] == 4:
    fingerImg = cv2.cvtColor(fingerImg, cv2.COLOR_BGRA2BGR)


while True:
    success, img = cap.read()
    img = detector.findHands(img)
    lmList = detector.findPosition(img, draw=False)

    if len(lmList) != 0:
        x1, y1 = lmList[4][1], lmList[4][2]
        x2, y2 = lmList[8][1], lmList[8][2]
        dist = math.hypot(x2 - x1, y2 - y1)
        cv2.line(img, (x1,y1), (x2, y2), (255, 0, 0), 3)
        cv2.putText(img, str(int(dist)), (750, 70), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 0, 0), 3)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 3)

        size = max(1, int(round(dist)))

        # Rectangle spanned by the two points (order agnostic)
        x_min, x_max = sorted((x1, x2))
        y_min, y_max = sorted((y1, y2))

        # Clamp to frame
        H, W = img.shape[:2]
        x_min = max(0, min(W - 1, x_min))
        y_min = max(0, min(H - 1, y_min))
        x_max = max(0, min(W, x_max))
        y_max = max(0, min(H, y_max))

        # Target size
        tw, th = x_max - x_min, y_max - y_min

        if tw > 0 and th > 0:
            # Stretch image to exactly fill the rectangle (aspect ratio will change)
            image_resized = cv2.resize(
                fingerImg, (tw, th),
                interpolation=cv2.INTER_LINEAR if (tw * th) >= (fingerImg.shape[1] * fingerImg.shape[0]) else cv2.INTER_AREA
            )

            # Paste with 100% opacity (overwrite ROI)
            img[y_min:y_max, x_min:x_max] = image_resized

            # Optional: draw the rectangle outline
            cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (255, 0, 0), 2)


    cTime = time.time()
    fps = 1 / (cTime - pTime)
    pTime = cTime



    cv2.putText(img, str(int(fps)), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 3)

    cv2.imshow("Image", img)
    cv2.waitKey(1)