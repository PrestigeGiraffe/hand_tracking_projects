import asyncio

import cv2
import mediapipe as mp
import time
import HandTrackingModule as htm
import os
import pygame
from collections import defaultdict

pTime = 0
cTime = 0
cap = cv2.VideoCapture(0)
detector = htm.handDetector()

pygame.mixer.init()
pygame.mixer.set_num_channels(64)

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
    0: (4, 2),     # thumb: tip 4 vs joint 2 (or 3 if you prefer)
    1: (8, 7),     # index
    2: (12, 11),   # middle
    3: (16, 15),   # ring
    # pinky optional: (20, 19)
}

def finger_is_down(tip, prev, lm):
    """Return True if tip is 'below' its previous joint (y larger)."""
    if tip not in lm or prev not in lm:
        return False
    if tip > 4:
        return lm[tip][1] > lm[prev][1]  # lm[id] = (x, y)
    else:
        return lm[tip][0] > lm[prev][0]  # for thumb

def detect_notes_this_frame(lm_right, currChord):
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
    return pressed

def play_frame(pressed_now, pressed_prev):
    new_presses = pressed_now - pressed_prev
    for key in new_presses:
        chords[key[0]][key[1]].play()
    return pressed_now.copy()  # the new pressed_prev

pressed_prev = set()


currChord = -1
chordVer = 0
while True:
    success, img = cap.read()
    img = detector.findHands(img)

    lmListRight = detector.findPosition(img, draw=False, handedness="Right")
    lmListLeft = detector.findPosition(img, draw=False, handedness="Left")

    # if len(lmList0) != 0:
    #     thumb1, thumb2 = lmList0[4], lmList0[2]
    #     index1, index2 = lmList0[8], lmList0[7]
    #     middle1, middle2 = lmList0[12], lmList0[11]
    #     ring1, ring2 = lmList0[16], lmList0[15]
    #     pinky1, pinky2 = lmList0[20], lmList0[19]
    #
    #     if currChord >= 0:
    #         if thumb1[1] > thumb2[1]:
    #             playNote(currChord, 0)
    #         if index1[2] > index2[2]:
    #             playNote(currChord, 1)
    #         if middle1[2] > middle2[2]:
    #             playNote(currChord, 2)
    #         if ring1[2] > ring2[2]:
    #             playNote(currChord, 3)
    #         if pinky1[2] > pinky2[2]:
    #             pass

    if len(lmListLeft) != 0:
        thumb1, thumb2 = lmListLeft[4], lmListLeft[2]
        index1, index2 = lmListLeft[8], lmListLeft[6]
        middle1, middle2 = lmListLeft[12], lmListLeft[10]
        ring1, ring2 = lmListLeft[16], lmListLeft[14]
        pinky1, pinky2 = lmListLeft[20], lmListLeft[18]

        h, w, c = img.shape
        x, y = w-IMAGE_X, 0

        if thumb1[1] < thumb2[1]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[0]
            currChord = 0
        elif index1[2] > index2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[1]
            currChord = 1
        elif middle1[2] > middle2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[2]
            currChord = 2
        elif ring1[2] > ring2[2]:
            img[y:y + IMAGE_Y, x:x + IMAGE_X] = overlayList[3]
            currChord = 3
        else:
            currChord = -1

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

    cv2.putText(img, str(int(fps)), (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 3)

    cv2.imshow("Image", img)
    cv2.waitKey(1)