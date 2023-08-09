# retrover - Retrospective Rover
A serial port monitor that makes it easy to see rare events and their context.

Watches multiple serial ports for rare events among line-oriented protocols.
Omits and/or compresses traffic that's not around those events.

## Usage

Pass serial port names as parameters:

```
pipenv run python retrover.py COM11
pipenv run python retrover.py COM11 COM7
pipenv run python retrover.py /dev/ttyUSB0
```

If multiple serial ports are provided, output is merged by line.

Press Ctrl+C once to see a summary of what's been seen so far, and again to quit.

Also set options below - directly in the script, for now.

`EVENT_PATTERN` is the main one: an array of strings to look for, or one regular expression.

## File output

The lines around events are written to `retrover.log` in the current directory, like this:

```
2023-08-07 14:35:45.968481 <  3.30 V
2023-08-07 14:35:46.115271  > ~S=4 ?=1 ?*
2023-08-07 14:35:47.210118  > ~S=4 ?=1 ?*
2023-08-07 14:35:47.210118  > OTA:
2023-08-07 14:35:47.312100  > ~S=7
2023-08-07 14:35:47.424675

== EVENT FOUND ==

2023-08-07 14:35:47.424675  > Up?
2023-08-07 14:35:48.520659  > No.
2023-08-07 14:35:48.617749  > ~S=5
2023-08-07 14:35:48.618748  > ~S=5 ?=1 ?*
2023-08-07 14:35:49.053728  > ~S=3
2023-08-07 14:35:49.546138  > ~S=3 ?=1 ?*
```

A timestamp is prefixed, and the `EVENT FOUND` marker is output just after each event.

A number of lines are included before and after the event equal to the `WINDOW_RADIUS` constant.

For two serial ports, lines from the first port listed on the command line are preceded by `< `,
and lines from the second one are preceded by ` >`. 

## Console output

All incoming data is displayed.

Each line is prefixed by the number of events seen so far.
