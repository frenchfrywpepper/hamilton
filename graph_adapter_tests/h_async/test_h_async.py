import asyncio
from unittest import mock

import pytest

from hamilton import base
from hamilton.experimental import h_async

from .resources import simple_async_module


async def async_identity(n: int) -> int:
    await asyncio.sleep(0.01)
    return n


@pytest.mark.asyncio
async def test_await_dict_of_coroutines():
    tasks = {n: async_identity(n) for n in range(0, 10)}
    results = await h_async.await_dict_of_tasks(tasks)
    assert results == {n: await async_identity(n) for n in range(0, 10)}


@pytest.mark.asyncio
async def test_await_dict_of_tasks():
    tasks = {n: asyncio.create_task(async_identity(n)) for n in range(0, 10)}
    results = await h_async.await_dict_of_tasks(tasks)
    assert results == {n: await async_identity(n) for n in range(0, 10)}


# The following are not parameterized as we need to use the event loop -- fixtures will complicate this
@pytest.mark.asyncio
async def test_process_value_raw():
    assert await h_async.process_value(1) == 1


@pytest.mark.asyncio
async def test_process_value_coroutine():
    assert await h_async.process_value(async_identity(1)) == 1


@pytest.mark.asyncio
async def test_process_value_task():
    assert await h_async.process_value(asyncio.create_task(async_identity(1))) == 1


@pytest.mark.asyncio
async def test_driver_end_to_end():
    dr = h_async.AsyncDriver({}, simple_async_module)
    all_vars = [var.name for var in dr.list_available_variables()]
    result = await dr.raw_execute(final_vars=all_vars, inputs={"external_input": 1})
    assert result == {
        "another_async_func": 8,
        "async_func_with_param": 4,
        "external_input": 1,
        "non_async_func_with_decorator": {"result_1": 9, "result_2": 5},
        "result_1": 9,
        "result_2": 5,
        "simple_async_func": 2,
        "simple_non_async_func": 7,
    }


@pytest.mark.asyncio
@mock.patch("hamilton.telemetry.send_event_json")
@mock.patch("hamilton.telemetry.g_telemetry_enabled", True)
async def test_driver_end_to_end_telemetry(send_event_json):
    dr = h_async.AsyncDriver({}, simple_async_module, result_builder=base.DictResult())
    with mock.patch("hamilton.telemetry.g_telemetry_enabled", False):
        # don't count this telemetry tracking invocation
        all_vars = [var.name for var in dr.list_available_variables()]
    result = await dr.execute(final_vars=all_vars, inputs={"external_input": 1})
    assert result == {
        "another_async_func": 8,
        "async_func_with_param": 4,
        "external_input": 1,
        "non_async_func_with_decorator": {"result_1": 9, "result_2": 5},
        "result_1": 9,
        "result_2": 5,
        "simple_async_func": 2,
        "simple_non_async_func": 7,
    }
    # to ensure the last telemetry invocation finishes executing
    # get all tasks -- and the current task, and await all others.
    try:
        # only works for 3.7+
        tasks = asyncio.all_tasks()
        current_task = asyncio.current_task()
        await asyncio.gather(*[t for t in tasks if t != current_task])
    except AttributeError:
        # required for 3.6
        await asyncio.sleep(1)
    assert send_event_json.called
    assert len(send_event_json.call_args_list) == 2
