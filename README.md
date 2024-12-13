# retrover - Retrospective Rover
A serial port monitor that makes it easy to see rare events and their context.

Watches multiple serial ports for rare events among line-oriented protocols.
Omits and/or compresses traffic that's not around those events.

## Usage

Pass serial port names as parameters:

```
pipenv run python retrover.py COM11 --regex "!!!!"
pipenv run python retrover.py COM11 COM7 --regex "(^No)|!!!!"
pipenv run python retrover.py /dev/ttyUSB0 --regex ^no !!!!
```

If multiple serial ports are provided, output is interleaved by line.

Press Ctrl+C once to see a summary of what's been seen so far, and again to quit.

## Command-line options

```
usage: retrover.py [-h] [--baud [BAUD]] [--log LOGFILE] [--window WINDOWRADIUS] [--windowSecs WINDOWSECS] [--eventrun]
                   [--delta] [--single] [--nopulse] --regex REGEX [REGEX ...] [--ignorecase] [--utc]
                   PORT [PORT ...]

Watch serial ports for events, and log them.

positional arguments:
  PORT                  a serial port to watch

options:
  -h, --help            show this help message and exit
  --baud [BAUD]         baud rate for all serial ports
  --log LOGFILE         file to log events to
  --window WINDOWRADIUS
                        Log this many lines before and after the event.
  --windowSecs WINDOWSECS
                        Log lines for this many seconds before and after the event.
  --eventrun            An event is counted for each run of lines that has any match.
  --delta               An event is counted for each match that's different from the previous line.
  --single              An event is counted for each match.
  --nopulse             An event is counted when there's been *no* match over the given window radius.
  --regex REGEX [REGEX ...]
                        A line that matches one or more regexes, anywhere, is an event.
  --ignorecase          whether to distinguish upper and lower case letters or not
  --utc                 whether to log times in UTC, vs. local time
```

If multiple event definition arguments ("An event is counted...") are specified, only the last one is used.
That is, there's only one way events are counted for each invocation of Retrover.

## File output

The lines around events are written to `retrover.log` in the current directory, like this:

```
2023-08-07 14:35:45.968481 <  3.30 V
2023-08-07 14:35:46.115271  > ~S=4 ?=1 ?*
2023-08-07 14:35:47.210118  > ~S=4 ?=1 ?*
2023-08-07 14:35:47.210118  > OTA:
2023-08-07 14:35:47.312100  > ~S=7
==
== EVENT FOUND (#1) ==
==
2023-08-07 14:35:47.424675  > Up?
2023-08-07 14:35:48.520659  > No.
2023-08-07 14:35:48.617749  > ~S=5
2023-08-07 14:35:48.618748  > ~S=5 ?=1 ?*
2023-08-07 14:35:49.053728  > ~S=3
2023-08-07 14:35:49.546138  > ~S=3 ?=1 ?*
```

A timestamp is prefixed, and the `== EVENT FOUND ==` marker is output just after each event.

A number of lines are included before and after the event equal to the `--window` argument.

For two serial ports, lines from the first port listed on the command line are preceded by `< `,
and lines from the second one are preceded by ` >`. 

If `--nopulse` is specified, lines that match the pulse are preceded by an asterisk (`*`).

## Console output

All incoming data is displayed.

Each line is prefixed by the number of events seen so far.

This allows you to monitor all the output as it passes by, while logging and counting only the real events.