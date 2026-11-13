"""Gradio Space entry point; FastAPI analysis routes share port 7860."""
import os
os.environ['KRATOS_PUBLIC_ANALYSIS']='true'
os.environ['KRATOS_BIND']='0.0.0.0'
os.environ['GRADIO_ANALYTICS_ENABLED']='False'
import gradio as gr
from server import app
# Keep API routes ahead of Gradio's catch-all. The main website lives on Pages.
app.router.routes=[r for r in app.router.routes if getattr(r,'name',None)!='dashboard']
with gr.Blocks(title='Kratos analysis service') as console:
    gr.Markdown('''# Kratos analysis service
Python analysis backend for [Kratos Stock Intelligence](https://samin110597-create.github.io/kratos-stock-intelligence/).

Market observations come from the named provider. Missing or outdated data is rejected for current analysis.

[Service health](/api/health) · [API documentation](/api/docs)
''')
if __name__=='__main__':
    console.launch(server_name='0.0.0.0', app_kwargs={'routes': app.router.routes, 'middleware': app.user_middleware})
