"""Tests for the in-process EventBus."""
import pytest

from alterego.kernel.event_bus import InProcessEventBus


@pytest.mark.asyncio
async def test_publish_subscribe_basic():
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe("mission.created", handler)
    await bus.publish("mission.created", {"id": "abc"})

    assert len(received) == 1
    assert received[0].subject == "mission.created"
    assert received[0].payload["id"] == "abc"


@pytest.mark.asyncio
async def test_wildcard_subscribe():
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    bus.subscribe("mission.*", handler)
    await bus.publish("mission.created", {"id": "1"})
    await bus.publish("mission.completed", {"id": "2"})
    await bus.publish("plugin.called", {"id": "3"})

    assert received == ["mission.created", "mission.completed"]


@pytest.mark.asyncio
async def test_star_subscribe_all():
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    bus.subscribe("*", handler)
    await bus.publish("mission.created", {})
    await bus.publish("plugin.called", {})

    assert len(received) == 2


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event)

    sub_id = bus.subscribe("mission.created", handler)
    await bus.publish("mission.created", {})
    assert len(received) == 1

    bus.unsubscribe(sub_id)
    await bus.publish("mission.created", {})
    assert len(received) == 1  # still 1


@pytest.mark.asyncio
async def test_handler_failure_doesnt_crash_bus():
    bus = InProcessEventBus()

    async def bad_handler(event):
        raise RuntimeError("boom")

    async def good_handler(event):
        good_handler.called = True

    good_handler.called = False

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)
    await bus.publish("test.event", {})

    assert good_handler.called
