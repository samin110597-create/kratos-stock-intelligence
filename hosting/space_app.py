"""Gradio Space entry point; FastAPI analysis routes share port 7860."""
import os
os.environ['KRATOS_PUBLIC_ANALYSIS']='true'
os.environ['KRATOS_BIND']='0.0.0.0'
os.environ['GRADIO_ANALYTICS_ENABLED']='False'
import gradio as gr
import spaces

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
model_id="Qwen/Qwen2.5-0.5B-Instruct"
tokenizer=AutoTokenizer.from_pretrained(model_id)
model=AutoModelForCausalLM.from_pretrained(model_id,torch_dtype=torch.float16).to("cuda")

@spaces.GPU(duration=60)
def explain_evidence(evidence):
    """Optional real model inference; not an upstream TradingAgents integration."""
    messages=[{"role":"system","content":"Explain only the supplied stock research evidence in plain English. Do not invent prices, facts, probabilities or accuracy. If evidence is missing say so. Do not give buy/sell instructions. This is an unvalidated small-model explanation, not a forecast."},{"role":"user","content":str(evidence)[:6000]}]
    text=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
    inputs=tokenizer(text,return_tensors="pt").to("cuda")
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=240,do_sample=False)
    return tokenizer.decode(output[0,inputs["input_ids"].shape[1]:],skip_special_tokens=True)

from server import app
# Keep API routes ahead of Gradio's catch-all. The main website lives on Pages.
app.router.routes=[r for r in app.router.routes if getattr(r,'name',None)!='dashboard']
with gr.Blocks(title='Kratos analysis service') as console:
    gr.Markdown('''# Kratos analysis service
Python analysis backend for [Kratos Stock Intelligence](https://samin110597-create.github.io/kratos-stock-intelligence/).

Market observations come from the named provider. Missing or outdated data is rejected for current analysis.

[Service health](/api/health) · [API documentation](/api/docs)
''')
    gr.Markdown('## Optional AI explanation\nQwen2.5-0.5B-Instruct · unvalidated explanation only · not TradingAgents. Uses free ZeroGPU quota when requested.')
    evidence=gr.Textbox(label='Evidence to explain',max_lines=12)
    explain=gr.Button('Explain supplied evidence')
    explanation=gr.Textbox(label='Model explanation — verify against the evidence')
    explain.click(explain_evidence,inputs=evidence,outputs=explanation,api_name='explain_evidence')
if __name__=='__main__':
    console.launch(server_name='0.0.0.0', app_kwargs={'routes': app.router.routes, 'middleware': app.user_middleware})
