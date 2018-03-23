import time
import json

wire_timeformat = "%Y-%m-%dT%H:%M:%Z"


def human_readable(epoch):
    return time.strftime(wire_timeformat, time.gmtime(epoch))


def parse_date(input_string, end=False):
    """
    Parse a date entered by a human like

    2018-03-21

    Arguments:
        input_string(str): the input
        end(bool): if False, the beginning of that day is returned,
            otherwise the end of that day is used.
    Returns:
        An int-based timestamp,
    """
    parse_format = "%Y-%m-%d"
    print('input_string', input_string)
    begin = time.mktime(time.strptime(input_string, parse_format))
    # add one day if required with end=True
    return begin if not end else begin + 24 * 3600


def input_default(message, default):
    prompt = f"{message} [{default}] : "
    return input(prompt) or default
