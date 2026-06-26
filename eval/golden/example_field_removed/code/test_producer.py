from producer import make_event


def test_make_event() -> None:
    assert make_event("launch").name == "launch"
