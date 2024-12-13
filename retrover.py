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
"""

import argparse
import os
import re
import sys
import time

from collections import deque
from datetime import datetime, timedelta

import serial


# Different ways we can trigger an event:
EVENT_MATCH = 'match'  # Simply if a regex is found in a line.
EVENT_DELTA = 'delta'  # If a regex is found, AND the line differs from the previously-found match.
EVENT_RUN = 'run'    # If a regex is found, AND there has not been a match in the previous args.windowRadius lines.
EVENT_NOPULSE = 'nopulse'   # If the regex hasn't been seen for args.windowTime seconds.


serialPortNames = []
serialPorts = []
numEvents = 0
previousMatchLine = ''


def _now():
    ''' Return the current time, in the configured timezone. '''
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
    elif len(serialPorts) <= 3:
        return ["< ", " >", "  "][i]
    else:
        return ""

log = deque([])
waitingForLogLines = 0;
def logLine(line, timestamp=True):
    ''' Add this line to a managed log, that will be dumped to a file only around events.
      If timestamp is False, omit the usual prefix of the date and time.
    '''
    global args, log, waitingForLogLines, saw_pulse
    log.append([_now() if timestamp else "", line, saw_pulse])
    print(numEvents, line)
    maybeOutput();

    # Remove lines we no longer need from the log.
    # If this line is a pulse, remove all the previous lines.
    # Keep the windowRadius at a minimum.
    while len(log) > args.windowRadius and (args.mode != EVENT_NOPULSE or saw_pulse):
        log.popleft()

def isOlderThanWindow(t, pad=0):
    ''' Return True if time t is longer ago than the window seconds argument.
        If pad is specified, extend the window by that many seconds.
    '''
    return t < (_now() - timedelta(seconds=args.windowSecs + pad))

def maybeOutput():
    ''' Write pending lines to the log file, and remove them from the log. '''
    global waitingForLogLines, log
    # Send output to the log file if we are still logging after an event.
    while waitingForLogLines and len(log):
        waitingForLogLines -= 1
        writeToFile(log.popleft())

def writeToFile(logEntry):
    global args, logFile
    line = str(logEntry[0])
    if line:
      line += ' ' + logEntry[1]
    else:
      line = logEntry[1]
    print(line, file=logFile)

def isEvent(line: str):
    ''' Return true iff line triggers an event.
        If we're looking for no-pulse and it *is* a pulse, set the global saw_pulse.
    '''
    global args, regexes, previousMatchLine, last_match_time, saw_pulse

    # See if we have a match.
    if any([regex.search(line) for regex in regexes]):
        if args.mode == EVENT_MATCH or args.mode == EVENT_RUN:
            return True
        elif args.mode == EVENT_DELTA:
            if line != previousMatchLine:
                previousMatchLine = line
                return True
        elif args.mode == EVENT_NOPULSE:
            last_match_time = _now()
            saw_pulse = True
    elif args.mode == EVENT_NOPULSE and isOlderThanWindow(last_match_time):
        return True
    return False

def logEvent():
    global args, log, waitingForLogLines, numEvents

    isInRun = args.mode == EVENT_RUN and waitingForLogLines > 0
    isInRun = isInRun or args.mode == EVENT_NOPULSE and len(log) == 0

    # Output an event separator if we're not currently showing an event.
    if not isInRun:
      writeToFile(["", ""])

    # Output all the lines that we already have saved.
    waitingForLogLines = len(log)
    maybeOutput()

    # Output some stuff about the event.
    if not isInRun:
      numEvents += 1
      logLine(f"==\n== EVENT FOUND (#{numEvents}) ==\n==", timestamp=False)
    printStats()
    
    # Note that we want to output another half-window of lines afterwards.
    waitingForLogLines = args.windowRadius

def processPort(i):
    # Read and echo a line from the given port.
    # Log events if they're found.
    # Return the line read; '' means there was a timeout and nothing was read.
    global numEvents, serialPorts, saw_pulse

    # Read the next line.
    thePort = serialPorts[i]

    try:
        line = thePort.readline().decode('utf-8')
    except UnicodeDecodeError:
        line = ' [bad Unicode decoding, maybe line noise?]'

    if line != '':
        line = line.strip()

        # Look for events.
        saw_pulse = False
        if (isEvent(line)):
            logLine(headerForPort(i) + ' ' + line)
            logEvent()
        else:
            logLine(headerForPort(i) + ('*' if saw_pulse else ' ') + line)

    return line


# Parse command-line arguments.
parser = argparse.ArgumentParser(description='Watch serial ports for events, and log them.')
parser.add_argument('serialPorts', metavar='PORT', nargs='+',
                    help='a serial port to watch')
parser.add_argument('--baud', nargs='?', default=9600, type=int,
                    help='baud rate for all serial ports')
parser.add_argument('--log', dest='logFileName', default='retrover.log',
                    help='file to log events to')
parser.add_argument('--clear', dest='clearLog', action='store_true',
                    help='whether to clear the log file at startup or append to existing content')
parser.add_argument('--window', dest='windowRadius', default=10, type=int,
                    help='Log this many lines before and after the event.')
parser.add_argument('--windowSecs', dest='windowSecs', default=16, type=int,
                    help='Log lines for this many seconds before and after the event.')

parser.add_argument('--eventrun', dest='mode', action='store_const', const=EVENT_RUN, default=EVENT_RUN,
                    help="An event is counted for each run of lines that has any match.")
parser.add_argument('--delta', dest='mode', action='store_const', const=EVENT_DELTA,
                    help="An event is counted for each match that's different from the previous line.")
parser.add_argument('--single', dest='mode', action='store_const', const=EVENT_MATCH,
                    help='An event is counted for each match.')
parser.add_argument('--nopulse', dest='mode', action='store_const', const=EVENT_NOPULSE,
                    help='An event is counted when there\'s been *no* match over the given window radius.')

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


# Other set up and banner.
regexes = [re.compile(r, re.IGNORECASE if args.ignorecase else 0) for r in args.regex]

with open(args.logFileName, ('w' if args.clearLog else 'a'), buffering=1) as logFile:
    print('', file=logFile)
    writeToFile([_now(), 'Start run.'])

    summary = "Searching for regexes: " + str(args.regex) + ", counting by " + args.mode
    if args.mode == EVENT_NOPULSE:
        summary += ' in ' + str(args.windowSecs) + ' sec'
    summary += ' with window radius ' + str(args.windowRadius)

    writeToFile([_now(), summary])
    print(summary);
    print("Press Ctrl+C to see stats.\n----")

    start_time = _now()
    last_match_time = _now()
    saw_pulse = False  # on the current line.


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


    # Cleanup.
    writeToFile([_now(), 'Closing.'])
