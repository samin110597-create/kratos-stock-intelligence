"""Read build errors with the deployment credential; never print credentials."""
import os,json,urllib.request
from collections import deque
secret=os.environ['HF_TOKEN']
for kind in ('build','run'):
    lines=deque(maxlen=80)
    try:
        req=urllib.request.Request('https://huggingface.co/api/spaces/Smit1105/kratos-backend/logs/'+kind,headers={'Authorization':'Bearer '+secret})
        with urllib.request.urlopen(req,timeout=8) as response:
            for i,raw in enumerate(response):
                line=raw.decode(errors='replace').strip()
                if line:lines.append(line.replace(secret,'[REDACTED]'))
                if i>12000:break
    except Exception as exc:print(kind,'log read ended:',type(exc).__name__)
    print(kind,'recent log lines:', '\n'.join(lines),flush=True)
