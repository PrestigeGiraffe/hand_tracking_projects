import HandTrackingModule as htm
import Microcontroller as mc
import cv2

detector = htm.handDetector()

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Cannot open webcam")

win = "Guitar Fingers"
cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)  # create window first

width = 1280
height = 720
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

while True:
    success, img = cap.read()
    if not success or img is None:
        continue

    img = detector.findHands(img)

    lmListLeft = detector.findPosition(img, handedness="Right")

    if len(lmListLeft) != 0:

        thumb1, thumb2 = lmListLeft[4], lmListLeft[2]
        index1, index2 = lmListLeft[8], lmListLeft[6]
        middle1, middle2 = lmListLeft[12], lmListLeft[10]
        ring1, ring2 = lmListLeft[16], lmListLeft[14]
        pinky1, pinky2 = lmListLeft[20], lmListLeft[18]

        allDown = False
        if thumb1[1] > thumb2[1] and index1[2] > index2[2] and middle1[2] > middle2[2] and ring1[2] > ring2[2] and \
                pinky1[2] > pinky2[2]:
            pass


        if thumb1[1] > thumb2[1]:
            pass
        if index1[2] > index2[2]:
            mc.pluckUp()
            print("index")
        if middle1[2] > middle2[2]:
            pass
        if ring1[2] > ring2[2]:
            pass
        else:
            mc.pluckDown()

    cv2.imshow(win, img)
    cv2.waitKey(1)





