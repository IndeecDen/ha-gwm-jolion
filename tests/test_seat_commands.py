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


def test_unsupported_heaters_fail_before_network():
    import ast
    import asyncio
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[1] / 'custom_components/gwm_jolion/coordinator.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'GwmJolionCoordinator')
    method = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'async_execute_command')
    scope = dict(UNSUPPORTED_COMMANDS=commands.UNSUPPORTED_COMMANDS, HomeAssistantError=RuntimeError, Any=object)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
    for key in commands.UNSUPPORTED_COMMANDS:
        with pytest.raises(RuntimeError, match='отключено'):
            asyncio.run(scope['async_execute_command'](SimpleNamespace(), key))


@pytest.mark.parametrize('fail', [None, 'engine', 'climate', 'seats'])
def test_comfort_sequence_stops_on_error_and_releases(fail):
    import ast
    import asyncio
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[1] / 'custom_components/gwm_jolion/coordinator.py'
    cls = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.ClassDef) and n.name == 'GwmJolionCoordinator')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'async_start_with_comfort')
    scope = dict(asyncio=asyncio, HomeAssistantError=RuntimeError, build_seat_heating_instructions=commands.build_seat_heating_instructions)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
    events=[]
    async def record(stage):
        events.append(stage)
        if stage == fail: raise RuntimeError('test failure')
    async def engine(*args, **kwargs): await record('engine')
    async def climate(**kwargs):
        assert kwargs['instructions']['0x04']['airConditioner']['temperature'] == '24'
        await record('climate')
    async def seats(*args):
        assert args == (3, 0, 10)
        await record('seats')
    async def pause(): events.append('pause')
    fake=SimpleNamespace(command_in_progress=False, _comfort_task=None, feature_enabled=lambda k:True,
        async_update_listeners=lambda:None, async_execute_command=engine, async_send_custom_t5=climate,
        async_set_seat_heating=seats, _async_comfort_pause=pause)
    task=scope['async_start_with_comfort'](fake, temperature=24, climate_time=15, engine_time=15, driver=3, passenger=0, seat_time=10)
    if fail:
        with pytest.raises(RuntimeError, match='не отменены'): asyncio.run(task)
    else: asyncio.run(task)
    expected=['engine','pause','climate','pause','seats']
    assert events == (expected[:expected.index(fail)+1] if fail else expected)
    assert fake._comfort_task is None
