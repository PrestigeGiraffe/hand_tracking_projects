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



# Video capture
pTime = 0
cTime = 0
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Camera not opened. Try indices 1, 2, or a different backend.")

win = "Guitar Fingers"
cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)  # create window first

width = 1280
height = 720
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)



# Initializing hand detector module
detector = htm.handDetector()

# Sound control initializations
pygame.mixer.init()
pygame.mixer.set_num_channels(64)
device = AudioUtilities.GetSpeakers()
deviceVolume = device.EndpointVolume  # IAudioEndpointVolume wrapper
volRange = deviceVolume.GetVolumeRange()
lowV, highV = volRange[0], volRange[1]


# Loading instruments
base_dir = os.path.dirname(__file__)
instruments = os.path.join(base_dir, "instruments")
valid_exts = {".wav", ".ogg", ".mp3"}

# Chord group variables
currChord = -1
chordVer = 1
chordGroup = 0
maxChordGroups = 0

chords_by_group = []

for inst in sorted([e for e in os.scandir(instruments) if e.is_dir()], key=lambda e: e.name):
    for g_entry in sorted([e for e in os.scandir(inst.path) if e.is_dir()], key=lambda e: e.name):
        group_dir = g_entry.path
        by_index = {}  # chord_idx -> [Sound, ...]
        for c_entry in sorted(
            [e for e in os.scandir(group_dir) if e.is_dir() and e.name.startswith("chord")],
            key=lambda e: e.name
        ):
            name = c_entry.name[5:]
            if name.isdigit():
                chord_idx = int(name)
                sounds = []
                for fname in sorted(os.listdir(c_entry.path)):
                    _, ext = os.path.splitext(fname)
                    if ext.lower() in valid_exts:
                        sounds.append(pygame.mixer.Sound(os.path.join(c_entry.path, fname)))
                by_index[chord_idx] = sounds
        max_idx = max(by_index.keys(), default=-1)
        chords_by_group.append([by_index.get(i, []) for i in range(max_idx + 1)])

maxChordGroups = len(chords_by_group)

# for instrument in os.scandir(instruments):
#     for group in os.scandir(instrument):
#         maxChordGroups += 1
#         chords_root = os.path.join(base_dir, group)
#         # Build: chords[0] -> sounds from folder "chord0", chords[1] -> "chord1", ...
#         _by_index = {}  # temp: idx -> [Sound, ...]
#         for entry in os.listdir(chords_root):
#             entry_path = os.path.join(chords_root, entry)
#             if not os.path.isdir(entry_path):
#                 continue
#             if not entry.startswith("chord"):
#                 continue
#             # parse numeric index after "chord"
#             try:
#                 idx = int(entry[5:])
#             except ValueError:
#                 continue
#
#             sounds = []
#             for fname in sorted(os.listdir(entry_path)):
#                 name, ext = os.path.splitext(fname)
#                 if ext.lower() in valid_exts:
#                     sounds.append(pygame.mixer.Sound(os.path.join(entry_path, fname)))
#             if sounds:
#                 _by_index[idx] = sounds




fingerPath = "FingerPositions"

overlayList = []  # 2D: [group][image]
for group in sorted(os.listdir(fingerPath)):
    group_dir = os.path.join(fingerPath, group)
    if not os.path.isdir(group_dir):
        continue
    chordsOverlayList = []
    for fname in sorted(os.listdir(group_dir)):
        im = cv2.imread(os.path.join(group_dir, fname), cv2.IMREAD_UNCHANGED)
        if im is None:
            continue
        # drop alpha if present so assignment works with BGR targets
        if im.ndim == 3 and im.shape[2] == 4:
            im = im[:, :, :3]
        chordsOverlayList.append(im)
    overlayList.append(chordsOverlayList)

IMAGE_X = 200
IMAGE_Y = 200

# Frame Debouncing
# ---- helpers ----
FINGER_TIPS_R = {  # right hand note mapping: note_index -> (tip_id, prev_joint_id)
    0: (4, 2),     # thumb: tip 4 vs joint 2 (or 3 if you prefer)
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

def detect_notes_this_frame(lm_right, group_idx, chord_idx, draw=True):
    pressed = set()
    if chord_idx < 0 or not lm_right:
        return pressed

    lm = {lid: (x, y) for (lid, x, y) in lm_right}
    bank = chords_by_group[group_idx]


    for note_idx, (tip, prev) in FINGER_TIPS_R.items():
        if finger_is_down(tip, prev, lm):
            print(len(chords_by_group))
            print(group_idx % maxChordGroups)
            print(chord_idx)
            print(len(bank))
            print("seperate")
            print(note_idx)
            print(len(bank[chord_idx]))
            if chord_idx < len(bank) and note_idx < len(bank[chord_idx]):
                pressed.add((chord_idx, note_idx))
                if draw and tip in lm:
                    finX, finY = lm[tip]
                    cv2.circle(img, (finX, finY), 15, (0, 255, 0), cv2.FILLED)
    return pressed


def play_frame(pressed_now, pressed_prev):
    new_presses = pressed_now - pressed_prev
    bank = chords_by_group[chordGroup % maxChordGroups]  # <<< add modulo
    for chord_idx, note_idx in new_presses:
        bank[chord_idx][note_idx].play()
    return pressed_now.copy()


pressed_prev = set()



#swipe Variables
prevPos = list()
currFrame = 0
prevLeftHand = list()
prevTime = 0
currTime = 0
swiped = False
COOLDOWN_TIME = 1.5
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

    if (currTime - cooldownCounter >= COOLDOWN_TIME):
        cv2.putText(img, str("Chord Group: ") + str(int(chordGroup+1)), (10, height - 100), cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 255, 255), 3)
    else:
        cv2.putText(img, str("Chord Group: ") + str(int(chordGroup+1)), (10, height - 100), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 0, 255), 3)

    if len(lmListLeft) != 0:
        thumb1, thumb2 = lmListLeft[4], lmListLeft[2]
        index1, index2 = lmListLeft[8], lmListLeft[6]
        middle1, middle2 = lmListLeft[12], lmListLeft[10]
        ring1, ring2 = lmListLeft[16], lmListLeft[14]
        pinky1, pinky2 = lmListLeft[20], lmListLeft[18]

        h, w, c = img.shape
        x, y = w-IMAGE_X, 0
        finX, finY = 0, 0

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
            finX, finY = thumb1[1], thumb1[2]
            currChord = 0
        elif index1[2] > index2[2]:
            finX, finY = index1[1], index1[2]
            currChord = 1
        elif middle1[2] > middle2[2]:
            finX, finY = middle1[1], middle1[2]
            currChord = 2
        elif ring1[2] > ring2[2]:
            finX, finY = ring1[1], ring1[2]
            currChord = 3
        else:
            currChord = -1

        img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[chordGroup][currChord]

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
                        if (chordGroup < maxChordGroups-1):
                            chordGroup += 1
                        else:
                            chordGroup = 0
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

        pressed_now = detect_notes_this_frame(lmListRight, chordGroup, currChord)
        pressed_prev = play_frame(pressed_now, pressed_prev)




    cTime = time.time()
    fps = 1 / (cTime - pTime)
    pTime = cTime

    cv2.putText(img, str("FPS: ") + str(int(fps)), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (50, 200, 50), 2)

    cv2.imshow(win, img)
    cv2.waitKey(1)