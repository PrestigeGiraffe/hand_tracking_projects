import cv2
import HandTrackingModule as htm
import pyfirmata2
import numpy as np

#Arduino Set Up
PORT = 'COM17'
PIN_SERVO1 = 9

board = pyfirmata2.Arduino(PORT)
board.servo_config(PIN_SERVO1)

def pluckDown():
    board.digital[PIN_SERVO1].write(180)

def pluckUp():
    board.digital[PIN_SERVO1].write(0)





# detector = htm.handDetector()

# cap = cv2.VideoCapture(0)
# if not cap.isOpened():
#     raise RuntimeError("Camera not opened. Try indices 1, 2, or a different backend.")
#
# # def map_diff_to_angle(diff, dmin=-150, dmax=150):
# #     # clamp diff then map to 0..180
# #     diff = np.clip(diff, dmin, dmax)
# #     return (diff - dmin) * 180.0 / (dmax - dmin)
#
# while True:
#     success, img = cap.read()
#     if not success:
#         break
#     img = detector.findHands(img)
#
#     lmListRight = detector.findPosition(img, handedness="Left")
#
#     if len(lmListRight) != 0:
#         tip = lmListRight[8]
#         end = lmListRight[5]
#         diff = abs(tip[1] - end[1])
#
#         angle = diff*10
#         board.digital[PIN_SERVO1].write(angle)
#
#
#
#     cv2.imshow("Arduino", img)
#     cv2.waitKey(1)
