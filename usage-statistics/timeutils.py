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
    # print('input_string', input_string)
    begin = time.mktime(time.strptime(input_string, parse_format))
    # add one day if required with end=True
    return begin if not end else begin + 24 * 3600


ifrom = None
iuntil = None

def show_period():
    global ifrom
    if ifrom is None:
        sfrom = input("Enter starting day yyyy-mm-dd : ")
        ifrom = parse_date(sfrom)
    print(f"period starts on {human_readable(ifrom)}")        
    global iuntil
    if iuntil is None:
        suntil = input("Enter ending day yyyy-mm-dd : ")
        iuntil = parse_date(suntil)
    print(f"period starts on {human_readable(iuntil)}")
    return ifrom, iuntil

        
