#!/usr/bin/env python3

"""
  Retrover - Retrospective rover

  Watches multiple serial ports for rare events among line-oriented protocols.
  Omits and/or compresses traffic that's not around those events.
  Copyright (c) 2019, 2023 by Six Mile Creek Systems LLC.

  Usage:

  Pass serial port names as parameters:
    pipenv run python retrover.py COM11
    pipenv run python retrover.py COM11 COM7
    pipenv run python retrover.py /dev/ttyUSB0

  Use -h or --help for more description of command-line arguments.

  Press Ctrl+C once to see a summary of what's been seen so far, and again to quit.

  Also set the options below - directly in this script; seems simpler for occasional use.
"""

import argparse
import os
import re
import sys
import time

from collections import deque
from datetime import datetime

import serial

# Configuration
# More of these could come from command-line arguments.
# I'm only using this for one thing at the moment, and I want to document the settings I used.

# The serial baud rate, shared across all ports.
COM_PORT_BAUD_RATE = 9600

# A single regex pattern to match, or a list of strings to match.
# Sought anywhere in the line, across all ports.
EVENT_PATTERN = ['(\~S=[^4])|(.*!!!!)|(.*\?\?)']

# Whether we're using regex matching or simple string matching.
USE_REGEX = True

# If not using regex, whether matching should be case-sensitive.
CASE_SENSITIVE = False

# Print this many lines before and after the event to the log.
WINDOW_RADIUS = 50

# Different ways we can trigger an event:
MATCH_EVENT = 1  # Simply if the EVENT_PATTERN is found in a line.
DELTA_EVENT = 2  # If the pattern is found, AND the line differs from the previously-found match.
EVENT_RUN = 3    # If the pattern is found, AND there has not been a match in the previous WINDOW_RADIUS lines.

EVENT_MODE = EVENT_RUN

# Whether to log times in UTC or local.
USE_UTC = False

serialPortNames = []
serialPorts = []
numEvents = 0
previousMatchLine = ''

def _now():
  if USE_UTC:
    return datetime.utcnow()
  else:
    return datetime.now()

def printStats():
    global numEvents

    total_time = _now() - start_time
    if numEvents:
        print("\n\nThere have been {} event(s) in {}, for an average time between of {}.\n".format(
            numEvents, total_time, total_time / (numEvents + 1)))
    else:
        print("\n\nThere have been no events in {}.".format(total_time))

def headerForPort(i):
    # Return the string to print at the start of each line to indicate what port it's from.
    if len(serialPorts) == 1:
        return ""
    elif len(serialPorts) == 2:
        return ["< ", " >"][i]
    else:
        return ""

log = deque([])
waitingForLogLines = 0;
def logLine(line):
    # Add this line to a managed log, that will be dumped to a file only around events.
    log.append([_now(), line])
    print(numEvents, line)
    maybeOutput();
    while len(log) > WINDOW_RADIUS:
        log.popleft()

def maybeOutput():
    global waitingForLogLines, log
    # Send output to the log file if we are still logging after an event.
    while waitingForLogLines and len(log):
        waitingForLogLines -= 1
        writeToFile(log.popleft())

def writeToFile(logEntry):
    global logFile
    print(logEntry[0], logEntry[1], file=logFile)

def isEvent(line: str):
    # Return true iff line triggers an event.
    global previousMatchLine

    # See if we have a match.
    if USE_REGEX:
      global regex
      result = regex.match(line)
    elif CASE_SENSITIVE:
      result = any([e in line for e in EVENT_PATTERN])
    else:
      result = any([e.lower() in line.lower() for e in EVENT_PATTERN])

    if result:
        if EVENT_MODE == MATCH_EVENT or EVENT_MODE == EVENT_RUN:
            return True
        elif EVENT_MODE == DELTA_EVENT:
            if line != previousMatchLine:
                previousMatchLine = line
                return True
    return False

def logEvent():
    global waitingForLogLines, numEvents

    isInRun = EVENT_MODE == EVENT_RUN and waitingForLogLines > 0

    # Output up to WINDOW_RADIUS lines that we already have.
    waitingForLogLines = WINDOW_RADIUS
    maybeOutput()

    # Output some stuff about the event.
    if not isInRun:
      numEvents += 1
      logLine("\n\n== EVENT FOUND ==\n")
    printStats()
    
    # Note that we want to output another half-window of lines afterwards.
    waitingForLogLines = WINDOW_RADIUS

def processPort(i):
    # Read and echo a line from the given port.
    # Log events if they're found.
    # Return it; '' means there was a timeout and nothing was read.
    global numEvents, serialPorts

    # Read the next line.
    thePort = serialPorts[i]

    try:
        line = thePort.readline().decode('utf-8')
    except UnicodeDecodeError:
        line = ' [bad Unicode decoding, maybe line noise?]'

    if line != '':
        line = line.strip()
        logLine(headerForPort(i) + ' ' + line)

        # Look for events.
        if (isEvent(line)):
            logEvent()

    return line


# Parse command-line arguments.
parser = argparse.ArgumentParser(description='Watch serial ports for events, and log them.')
parser.add_argument('serialPorts', metavar='PORT', nargs='+',
                    help='a serial port to watch')
parser.add_argument('--log', dest='logFileName', nargs='?', default='retrover.log',
                    help='file to log events to')

args = parser.parse_args()

# Serial port setup
for nextPort in args.serialPorts:
    print("Connecting to serial port '{}'.".format(nextPort))
    serialPortNames.append(nextPort)
    serialPorts.append(serial.Serial(nextPort, COM_PORT_BAUD_RATE, timeout=0.1))

if USE_REGEX:
  regex = re.compile(EVENT_PATTERN[0])

# Open the log file.
logFile = open(args.logFileName, mode='a', buffering=1)

print('', file=logFile)
writeToFile([_now(), 'Start run.'])

summary = "Searching for: " + str(EVENT_PATTERN) + (" as regex" if USE_REGEX else "")
writeToFile([_now(), summary])

print(summary);
print("Press Ctrl+C to see stats.\n----")

start_time = _now()

# Read loop
try:
    while True:
        try:
            for port in range(len(serialPorts)):
                while processPort(port):
                    pass

        except KeyboardInterrupt:
            printStats()
            print("Press Ctrl+C again to quit.")
            time.sleep(3)
except KeyboardInterrupt:
    pass

writeToFile([_now(), 'Closing.'])
