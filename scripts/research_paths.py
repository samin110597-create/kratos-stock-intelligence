"""Reproducible personal-history experiment; output is private/ignored by default."""
import argparse
import json
from pathlib import Path
import yfinance as yf
from kratos.data import valid_symbol,tidy
from kratos.technicals import only_closed_daily
from kratos.target_paths import walk_forward_paths

def main():
    p=argparse.ArgumentParser();p.add_argument('symbol');p.add_argument('--cost-bps',type=float,default=20)
    args=p.parse_args();symbol=valid_symbol(args.symbol)
    if not 0<=args.cost_bps<=1000: p.error('Cost must be 0 to 1000 basis points')
    frame=only_closed_daily(tidy(yf.Ticker(symbol).history(period='10y',interval='1d',auto_adjust=False,timeout=20)),symbol=symbol)
    if frame.empty: raise ValueError('No actual market history returned')
    out=Path('data/research-check');out.mkdir(parents=True,exist_ok=True)
    frame.to_csv(out/(symbol+'-actual-history.csv'))
    for h in (5,20):
        result=walk_forward_paths(frame,h,cost_bps=args.cost_bps)
        (out/f'{symbol}-paths-{h}.json').write_text(json.dumps(result,allow_nan=False))
        print(json.dumps({'symbol':symbol,'horizon':h,'last_closed':str(frame.index[-1]),'metrics':result['metrics'],'promoted':False}))
if __name__=='__main__':main()
