"""Small per-symbol pointers for revisiting the last completed results."""
from pathlib import Path
import json
import os

root = Path('site/data/requested')
for symbol in root.iterdir():
    if not symbol.is_dir():
        continue
    for engine in ('qlib','tradingagents','lean'):
        records = sorted(symbol.glob('????-??-??/'+engine+'.json'))
        if records:
            last = records[-1]
            pointer = symbol/('latest-'+engine+'.json')
            pointer.write_text(json.dumps({'symbol':symbol.name,'session':last.parent.name})+'\n')
