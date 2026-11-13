"""Publish a source allowlist only. Never upload env files, credentials or local state."""
import os
import tempfile
from pathlib import Path
import shutil
from huggingface_hub import HfApi
ROOT=Path(__file__).resolve().parents[1]
api=HfApi(token=os.environ['HF_TOKEN'])
repo='Smit1105/kratos-backend'
info=api.space_info(repo)
hardware=getattr(info.runtime,'hardware',None)
requested=getattr(info.runtime,'requested_hardware',None)
if str(requested or hardware) not in ('zero-a10g','SpaceHardware.ZERO_A10G'):
    raise RuntimeError('Deployment stopped: expected existing ZeroGPU hardware. No hardware changes made.')
with tempfile.TemporaryDirectory() as folder:
    dest=Path(folder)
    for directory in ('kratos','scripts','site'):
        shutil.copytree(ROOT/directory,dest/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env','*.sqlite*'))
    for name in ('server.py','requirements.txt'):
        shutil.copy2(ROOT/name,dest/name)
    shutil.copy2(ROOT/'hosting/space_app.py',dest/'space_app.py')
    shutil.copy2(ROOT/'hosting/README.md',dest/'README.md')
    (dest/'SOURCE_REVISION').write_text(os.environ['GITHUB_SHA']+'\n')
    api.upload_folder(repo_id=repo,repo_type='space',folder_path=folder,
        commit_message='Deploy canonical GitHub revision '+os.environ['GITHUB_SHA'])
print('Source uploaded to Smit1105/kratos-backend; hardware unchanged.')
