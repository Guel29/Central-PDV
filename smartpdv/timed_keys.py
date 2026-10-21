"""Bounded numeric keyboard bursts, never USB/HID redirection.

Only observed key transitions and relative times travel in RAM over the existing
authenticated connection. No text conversion, invented suffix or acceleration.
"""
import time


def valid_sequence(event):
    if not isinstance(event, dict) or set(event) != {'kind', 'events'} or event['kind'] != 'key_sequence':
        return False
    events = event['events']
    if not isinstance(events, list) or not 8 <= len(events) <= 64:
        return False
    held, digits, last, ending = set(), 0, 0, False
    for i, item in enumerate(events):
        if not isinstance(item, dict) or set(item) != {'key', 'code', 'action', 'at_ms'}:
            return False
        key, code, action, stamp = (item[k] for k in ('key', 'code', 'action', 'at_ms'))
        if type(stamp) is not int or not last <= stamp <= 250 or i == 0 and stamp != 0:
            return False
        last = stamp
        if not isinstance(key, str) or not isinstance(code, str):
            return False
        digit = len(key) == 1 and key in '0123456789' and code in ('Digit'+key, 'Numpad'+key)
        enter = key == 'Enter' and code in ('Enter', 'NumpadEnter')
        if not digit and not enter or digit and ending or action not in ('down', 'up'):
            return False
        if action == 'down':
            if held or enter and (digits < 4 or i != len(events)-2):
                return False
            held.add(code)
            digits += int(digit)
            ending = enter
        elif code not in held:
            return False
        else:
            held.remove(code)
    return not held and digits >= 4


def replay(events, send, clock=time.perf_counter, sleep=time.sleep):
    """Keep observed offsets; OS scheduling can add delay. Maximum span: 250 ms."""
    started = clock()
    for event in events:
        remaining = started + event['at_ms']/1000 - clock()
        if remaining > 0:
            sleep(remaining)
        send(event)
