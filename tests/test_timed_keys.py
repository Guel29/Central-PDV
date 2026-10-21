import copy
import pytest
from smartpdv.timed_keys import valid_sequence, replay
from smartpdv.windows import Desktop
from smartpdv.key_codes import PHYSICAL_SCANS


def sequence(value='001234567890', suffix='Enter'):
    events=[]
    for index, key in enumerate(list(value)+([suffix] if suffix else [])):
        code='Digit'+key if key.isdigit() else key
        for offset,action in enumerate(('down','up')):
            events.append(dict(key=key,code=code,action=action,at_ms=index*4+offset))
    return dict(kind='key_sequence',events=events)


def test_validator_preserves_zeros_numpad_and_only_observed_suffix():
    event=sequence(suffix=None)
    assert valid_sequence(event)
    for item in event['events']:
        item['code']='Numpad'+item['key']
    assert valid_sequence(event)
    event=sequence(suffix='Enter')
    for item in event['events'][-2:]: item['code']='NumpadEnter'
    assert valid_sequence(event)


@pytest.mark.parametrize('mutation',[
    lambda e:e['events'].pop(),
    lambda e:e['events'][0].update(at_ms=1),
    lambda e:e['events'][-1].update(at_ms=251),
    lambda e:e['events'][2].update(at_ms=-1),
    lambda e:e['events'][0].update(at_ms=False),
    lambda e:e['events'][0].update(at_ms=0.0),
    lambda e:e['events'][0].update(code='KeyA'),
    lambda e:e['events'][0].update(code=[]),
    lambda e:e['events'][0].update(action='up'),
    lambda e:e['events'][1].update(action='down'),
    lambda e:e['events'][0].update(extra='secret'),
    lambda e:e['events'][0].update(key='Enter',code='Enter'),
    lambda e:e.update(events=e['events']*20),
    lambda e:e.update(text='secret'),
])
def test_rejects_unbalanced_unbounded_modified_or_non_numeric_sequence(mutation):
    event=sequence();mutation(event)
    assert not valid_sequence(event)


def test_replay_uses_original_offsets_without_minimum_hold_or_added_enter():
    event=sequence(suffix=None);now=[10.0];observed=[]
    def sleep(seconds): now[0]+=seconds
    replay(event['events'],lambda e:observed.append((copy.copy(e),now[0])),lambda:now[0],sleep)
    assert [e for e,t in observed]==event['events']
    assert [t-10 for e,t in observed]==pytest.approx([e['at_ms']/1000 for e in event['events']])


def test_desktop_replay_cleans_up_rejected_key_without_releasing_mouse(monkeypatch):
    desktop=Desktop.__new__(Desktop);desktop.held_keys={};desktop.held_buttons={0}
    events=[]
    class Keyboard:
        def send(self,scan,down,*,preserve_timing=False):
            assert preserve_timing
            events.append((scan,down))
            if len(events)==2: raise OSError(5,'test refusal')
    desktop.keyboard=Keyboard()
    monkeypatch.setattr('smartpdv.windows.replay',lambda items,send:[send(e) for e in items])
    with pytest.raises(OSError): desktop.input(sequence())
    assert events==[(PHYSICAL_SCANS['Digit0'],True),(PHYSICAL_SCANS['Digit0'],False),(PHYSICAL_SCANS['Digit0'],False)]
    assert not desktop.held_keys
    assert desktop.held_buttons=={0}


def test_desktop_does_not_replay_with_existing_modifiers_or_invalid_sequence():
    desktop=Desktop.__new__(Desktop);desktop.held_keys={'ShiftLeft':0x2a}
    assert desktop.input(sequence()) is False
    desktop.held_keys={}
    assert desktop.input({'kind':'key_sequence','events':[]}) is False
