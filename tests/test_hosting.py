"""API contracts must survive embedding in the Gradio hosting application."""
import gradio as gr
from gradio.routes import App
from fastapi.testclient import TestClient
from server import app


def test_space_api_routes_and_cors_survive_gradio(monkeypatch):
    monkeypatch.setenv('KRATOS_BIND','0.0.0.0')
    monkeypatch.delenv('KRATOS_ACCESS_TOKEN',raising=False)
    with gr.Blocks() as demo:
        gr.Markdown('Hosting contract test')
    routes=[r for r in app.router.routes if getattr(r,'name',None)!='dashboard']
    combined=App.create_app(demo,app_kwargs={'routes':routes,'middleware':app.user_middleware})
    client=TestClient(combined)
    response=client.get('/api/health',headers={'Origin':'https://samin110597-create.github.io'})
    assert response.status_code==200
    assert response.json()['status']=='ok'
    assert response.headers['access-control-allow-origin']=='https://samin110597-create.github.io'
    assert response.headers['cache-control']=='no-store'
    assert client.get('/api/providers').status_code==503
