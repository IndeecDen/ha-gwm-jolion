import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('seat_commands', Path(__file__).resolve().parents[1] / 'custom_components/gwm_jolion/commands.py')
commands = importlib.util.module_from_spec(spec)
spec.loader.exec_module(commands)


def test_seat_levels_and_minutes():
    seat = commands.build_seat_heating_instructions(3, 1, 5)['0x0A']['seat']
    assert seat == dict(operationMode='1', switchOrder='1', operationTime='5', leftFront='3', rightFront='1')
    assert commands.build_seat_heating_instructions(0, 2, 1)['0x0A']['seat']['rightFront'] == '2'
    assert 'rightFront' not in commands.build_seat_heating_instructions(1, None, 10)['0x0A']['seat']


def test_seat_global_off():
    seat = commands.build_seat_heating_instructions(0, 0, 5)['0x0A']['seat']
    assert seat['switchOrder'] == '2'
    assert seat['operationTime'] == '0'
    assert all(seat[key] == '0' for key in ('leftFront', 'rightFront', 'leftBack', 'rightBack'))


@pytest.mark.parametrize('driver,passenger,time', [(4,0,5),(-1,0,5),(True,0,5),(1.5,0,5),(1,0,0),(1,0,11),(1,0,5.5),(None,None,5)])
def test_reject_invalid_seat_settings(driver, passenger, time):
    with pytest.raises(ValueError):
        commands.build_seat_heating_instructions(driver, passenger, time)


def test_window_positions_match_android():
    assert commands.COMMANDS['close_windows']['instructions'] == {'0x08': {'window': dict(leftFront=0,leftBack=0,rightFront=0,rightBack=0)}}
    assert set(commands.COMMANDS['open_windows']['instructions']['0x08']['window'].values()) == {3}
