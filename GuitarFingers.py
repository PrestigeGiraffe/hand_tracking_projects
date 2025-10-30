import asyncio

import cv2, tkinter as tk
import mediapipe as mp
import time
import numpy as np
from Scripts.activate_this import prev_length

from numpy.ma.core import filled
from scipy.constants import milli

import HandTrackingModule as htm
import os
import pygame
import math
from collections import defaultdict

from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from collections import deque

# import Microcontroller as mc

pTime = 0
cTime = 0
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Camera not opened. Try indices 1, 2, or a different backend.")

win = "Guitar Fingers"
cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)  # create window first




detector = htm.handDetector()

pygame.mixer.init()
pygame.mixer.set_num_channels(64)


device = AudioUtilities.GetSpeakers()
deviceVolume = device.EndpointVolume  # IAudioEndpointVolume wrapper

volRange = deviceVolume.GetVolumeRange()
lowV, highV = volRange[0], volRange[1]



base_dir = os.path.dirname(__file__)
chords_root = os.path.join(base_dir, "chords")
valid_exts = {".wav", ".ogg", ".mp3"}

# Build: chords[0] -> sounds from folder "chord0", chords[1] -> "chord1", ...
_by_index = {}  # temp: idx -> [Sound, ...]
for entry in os.listdir(chords_root):
    entry_path = os.path.join(chords_root, entry)
    if not os.path.isdir(entry_path):
        continue
    if not entry.startswith("chord"):
        continue
    # parse numeric index after "chord"
    try:
        idx = int(entry[5:])
    except ValueError:
        continue

    sounds = []
    for fname in sorted(os.listdir(entry_path)):
        name, ext = os.path.splitext(fname)
        if ext.lower() in valid_exts:
            sounds.append(pygame.mixer.Sound(os.path.join(entry_path, fname)))
    if sounds:
        _by_index[idx] = sounds

# Convert sparse dict to dense list indexed by chord number
max_idx = max(_by_index.keys(), default=-1)
chords = [ _by_index.get(i, []) for i in range(max_idx + 1) ]

fingerPath = "FingerPositions"
fingerPositions = os.listdir(fingerPath)
overlayList = []
for imPath in fingerPositions:
    imPath = cv2.imread(f'{fingerPath}/{imPath}')
    overlayList.append(imPath)

IMAGE_X = 200
IMAGE_Y = 200

# Frame Debouncing
# ---- helpers ----
FINGER_TIPS_R = {  # right hand note mapping: note_index -> (tip_id, prev_joint_id)
    0: (4, 1),     # thumb: tip 4 vs joint 2 (or 3 if you prefer)
    1: (8, 6),     # index
    2: (12, 10),   # middle
    3: (16, 14),   # ring
    # pinky optional: (20, 19)
}

def finger_is_down(tip, prev, lm):
    """Return True if tip is 'below' its previous joint (y larger)."""
    if tip not in lm or prev not in lm:
        return False
    if tip > 4:

        return lm[tip][1] > lm[prev][1]  # lm[id] = (x, y)

    else:
        return lm[tip][0] < lm[prev][0]  # for thumb

def detect_notes_this_frame(lm_right, currChord, draw=True):
    """
    Build the set of (chord, note) currently pressed by the RIGHT hand.
    lm_right: list like [[id, x, y], ...] from your HandTrackingModule for the right hand.
    """
    pressed = set()
    if currChord < 0 or not lm_right:
        return pressed

    # quick lookup: id -> (x, y)
    lm = {lid: (x, y) for (lid, x, y) in lm_right}

    for note_idx, (tip, prev) in FINGER_TIPS_R.items():
        if finger_is_down(tip, prev, lm):
            # only add if that note exists in this chord bank
            if currChord < len(chords) and note_idx < len(chords[currChord]):
                pressed.add((currChord, note_idx))

                if draw and tip in lm:
                    finX, finY = lm[tip]
                    cv2.circle(img, (finX, finY), 15, (0, 255, 0), cv2.FILLED)

    return pressed

def play_frame(pressed_now, pressed_prev):
    new_presses = pressed_now - pressed_prev
    for key in new_presses:
        chords[key[0]][key[1]].play()
    return pressed_now.copy()  # the new pressed_prev


pressed_prev = set()

# Chord group variables
currChord = -1
chordVer = 1
chordGroup = 0
maxChordGroups = 3

#swipe Variables
prevPos = list()
currFrame = 0
prevLeftHand = list()
prevTime = 0
swiped = False
COOLDOWN_TIME = 2
cooldownCounter = 0


# loop through chord folder to get max chord groups

async def debounce(time):
    time.sleep(time)
    swipeDebounce = True

while True:
    success, img = cap.read()
    if not success or img is None:
        continue

    currFrame+=1
    img = detector.findHands(img)

    lmListLeft = detector.findPosition(img, handedness="Right")
    lmListRight = detector.findPosition(img, handedness="Left")

    if len(lmListLeft) != 0:
        thumb1, thumb2 = lmListLeft[4], lmListLeft[2]
        index1, index2 = lmListLeft[8], lmListLeft[6]
        middle1, middle2 = lmListLeft[12], lmListLeft[10]
        ring1, ring2 = lmListLeft[16], lmListLeft[14]
        pinky1, pinky2 = lmListLeft[20], lmListLeft[18]

        h, w, c = img.shape
        x, y = w-IMAGE_X, 0
        finX, finY = 0, 0

        allDown = False
        if thumb1[1] > thumb2[1] and index1[2] > index2[2] and middle1[2] > middle2[2] and ring1[2] > ring2[2] and \
                pinky1[2] > pinky2[2]:
            if len(lmListRight) != 0:
                currChord = -1


                # Right Hand Finger Tips and UI
                x1, y1 = lmListRight[4][1], lmListRight[4][2]
                x2, y2 = lmListRight[8][1], lmListRight[8][2]
                dist = math.hypot(x2 - x1, y2 - y1)
                cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 3)

                # Volume UI
                vBarW, vBarH = 20, 200
                vBarX, vBarY = 10, 200
                cv2.rectangle(img, (vBarX, vBarY), (vBarX+vBarW, vBarY+vBarH), (100, 100, 100), 3)
                volume = dist/vBarH * 100 - h/50
                volume = max(0, min(volume, 100))
                cv2.putText(img, str("Volume: ")+str(int(volume))+str("%"), (vBarX, vBarH+vBarY+50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 100), 3)
                cv2.rectangle(img, (vBarX, vBarY+vBarH-int(vBarH*volume/100)), (vBarX+vBarW, vBarY+vBarH), (100, 255, 100), cv2.FILLED)


                vol_scalar = volume/100

                deviceVolume.SetMasterVolumeLevelScalar(vol_scalar, None)

        elif thumb1[1] > thumb2[1]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[0]
            finX, finY = thumb1[1], thumb1[2]
            currChord = 0
        elif index1[2] > index2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[1]
            finX, finY = index1[1], index1[2]
            currChord = 1
        elif middle1[2] > middle2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[2]
            finX, finY = middle1[1], middle1[2]
            currChord = 2
        elif ring1[2] > ring2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[3]
            finX, finY = ring1[1], ring1[2]
            currChord = 3
        else:
            currChord = -1

        # Check for swipe

        if currFrame % 5 == 0:
            currTime = time.time()
            swipePoint = lmListLeft[12][1]
            if prevLeftHand and len(prevPos) > 1:
                swipeSpeed = (swipePoint-prevPos[-1]) / (currTime - prevTime)
                if abs(swipeSpeed) > 700 and currTime-cooldownCounter >= COOLDOWN_TIME:
                    if swipeSpeed < 0:
                        swiped = True
                        cooldownCounter = time.time()
                        if (chordGroup < maxChordGroups):
                            chordGroup += 1
                        else:
                            chordGroup = 0
                        print(chordGroup)
                    else:
                        print("swiped left")
                else:
                    swiped = False

            prevTime = currTime
            prevPos.append(swipePoint)
            # Only keep 30 frames in cycle
            if len(prevPos) > 30:
                prevPos.pop(0)

            prevLeftHand = lmListLeft
            prevTime = time.time()






    if currChord >= 0:
        cv2.circle(img, (finX, finY), 15, (0, 0, 255), cv2.FILLED)

        if pinky1[2] > pinky2[2]:
            chordVer = 1
        else:
            chordVer = 0


        # 3) Build pressed_now from RIGHT hand; NO direct play() calls here
        pressed_now = detect_notes_this_frame(lmListRight, currChord)

        # 4) Edge-trigger playback
        pressed_prev = play_frame(pressed_now, pressed_prev)




    cTime = time.time()
    fps = 1 / (cTime - pTime)
    pTime = cTime

    cv2.putText(img, str("FPS: ") + str(int(fps)), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (50, 200, 50), 2)

    cv2.imshow("Guitar Fingers", img)
    cv2.setWindowProperty("Guitar Fingers", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.waitKey(1)