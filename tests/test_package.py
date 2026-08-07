def test_package_exposes_version():
    import safepatch

    assert isinstance(safepatch.__version__, str)
    assert safepatch.__version__
