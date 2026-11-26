import verbatim


def test_package_exposes_version() -> None:
    assert isinstance(verbatim.__version__, str)
