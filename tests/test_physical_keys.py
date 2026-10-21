"""Regression: a keypad digit must not become a top-row digit."""
import pytest
from smartpdv.windows import Desktop


class Keyboard:
    def __init__(self):
        self.events=[]
    def send(self,scan,down):
        self.events.append((scan,down))
    def character(self,key):
        return ord(key.upper())
    def resolve(self,vk):
        return {49:0x02,13:0x1c,91:0xe05b}[vk]


@pytest.mark.parametrize('key,code,scan',[
    ('1','Digit1',0x02),('1','Numpad1',0x4f),('Enter','Enter',0x1c),
    ('Enter','NumpadEnter',0xe01c),('Control','ControlRight',0xe01d),
    ('Meta','MetaLeft',0xe05b),('Meta','MetaRight',0xe05c),
    ('Shift','ShiftLeft',0x2a),('Shift','ShiftRight',0x36)])
def test_agent_preserves_physical_key_and_releases_it(key,code,scan):
    desktop=Desktop.__new__(Desktop)
    desktop.keyboard=Keyboard();desktop.held_keys={};desktop.held_buttons=set()
    assert desktop.input(dict(kind='key',action='down',key=key,code=code))
    desktop.release()
    assert desktop.keyboard.events==[(scan,True),(scan,False)]
    assert not desktop.held_keys


def test_agent_accepts_older_central_without_code():
    desktop=Desktop.__new__(Desktop)
    desktop.keyboard=Keyboard();desktop.held_keys={};desktop.held_buttons=set()
    assert desktop.input(dict(kind='key',action='down',key='1'))
    assert desktop.input(dict(kind='key',action='up',key='1'))
    assert desktop.keyboard.events==[(0x02,True),(0x02,False)]


def test_left_and_right_modifiers_do_not_replace_each_other():
    desktop=Desktop.__new__(Desktop)
    desktop.keyboard=Keyboard();desktop.held_keys={};desktop.held_buttons=set()
    for code in ('ShiftLeft','ShiftRight'):
        desktop.input(dict(kind='key',action='down',key='Shift',code=code))
    desktop.release()
    assert desktop.keyboard.events==[(0x2a,True),(0x36,True),(0x2a,False),(0x36,False)]
