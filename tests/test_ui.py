"""Import/render smoke test for the Gradio 6 application (no market HTTP calls)."""
def test_build_ui():
    from app import build_app
    app = build_app()
    assert app is not None
