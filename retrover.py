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


# Different ways we can trigger an event:
EVENT_MATCH = 'match'  # Simply if a regex is found in a line.
EVENT_DELTA = 'delta'  # If a regex is found, AND the line differs from the previously-found match.
EVENT_RUN = 'run'    # If a regex is found, AND there has not been a match in the previous args.windowRadius lines.


serialPortNames = []
serialPorts = []
numEvents = 0
previousMatchLine = ''


def _now():
    global args
    if args.utc:
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
def logLine(line, timestamp=True):
    ''' Add this line to a managed log, that will be dumped to a file only around events.
      If timestamp is False, omit the usual prefix of the date and time.
    '''
    global args
    log.append([_now() if timestamp else "", line])
    print(numEvents, line)
    maybeOutput();
    while len(log) > args.windowRadius:
        log.popleft()

def maybeOutput():
    global waitingForLogLines, log
    # Send output to the log file if we are still logging after an event.
    while waitingForLogLines and len(log):
        waitingForLogLines -= 1
        writeToFile(log.popleft())

def writeToFile(logEntry):
    global logFile
    line = str(logEntry[0])
    if line:
      line += ' ' + logEntry[1]
    else:
      line = logEntry[1]
    print(line, file=logFile)

def isEvent(line: str):
    # Return true iff line triggers an event.
    global args, regexes, previousMatchLine

    # See if we have a match.
    if any([regex.search(line) for regex in regexes]):
        if args.mode == EVENT_MATCH or args.mode == EVENT_RUN:
            return True
        elif args.mode == EVENT_DELTA:
            if line != previousMatchLine:
                previousMatchLine = line
                return True
    return False

def logEvent():
    global args, waitingForLogLines, numEvents

    isInRun = args.mode == EVENT_RUN and waitingForLogLines > 0

    # Output an event separator if we're not currently showing an event.
    if not isInRun:
      writeToFile(["", ""])

    # Output up to args.windowRadius lines that we already have.
    waitingForLogLines = args.windowRadius
    maybeOutput()

    # Output some stuff about the event.
    if not isInRun:
      numEvents += 1
      logLine("==\n== EVENT FOUND ==\n==", timestamp=False)
    printStats()
    
    # Note that we want to output another half-window of lines afterwards.
    waitingForLogLines = args.windowRadius

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
parser.add_argument('--baud', nargs='?', default=9600,
                    help='baud rate for all serial ports')
parser.add_argument('--log', dest='logFileName', nargs='?', default='retrover.log',
                    help='file to log events to')
parser.add_argument('--window', dest='windowRadius', default=10,
                    help='Log this many lines before and after the event.')

parser.add_argument('--eventrun', dest='mode', action='store_const', const=EVENT_RUN, default=EVENT_RUN,
                    help="An event is counted for each run of lines that has any match.")
parser.add_argument('--delta', dest='mode', action='store_const', const=EVENT_DELTA,
                    help="An event is counted for each match that's different from the previous line.")
parser.add_argument('--single', dest='mode', action='store_const', const=EVENT_MATCH,
                    help='An event is counted for each match.')

parser.add_argument('--regex', nargs='+', required=True, action='extend',
                    help='A line that matches one or more regexes, anywhere, is an event.')

parser.add_argument('--ignorecase', action='store_true',
                    help='whether to distinguish upper and lower case letters or not')
parser.add_argument('--utc', action='store_true',
                    help='whether to log times in UTC, vs. local time')

args = parser.parse_args()

# Serial port setup
for nextPort in args.serialPorts:
    print("Connecting to serial port '{}'.".format(nextPort))
    serialPortNames.append(nextPort)
    serialPorts.append(serial.Serial(nextPort, args.baud, timeout=0.1))

regexes = [re.compile(r, re.IGNORECASE if args.ignorecase else 0) for r in args.regex]

# Open the log file.
logFile = open(args.logFileName, mode='a', buffering=1)

print('', file=logFile)
writeToFile([_now(), 'Start run.'])

summary = "Searching for regexes: " + str(args.regex) + ", counting by " + args.mode
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
