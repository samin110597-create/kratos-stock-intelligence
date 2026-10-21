"""Print statuses only. No raw provider data, URLs or credentials in CI logs."""
from kratos.connectors import Connectors, status, ConnectorError

def main():
    client=Connectors()
    for name,info in status().items():
        if not info['configured']:
            print(name+': NOT CONFIGURED');continue
        try:
            result=client.fetch(name,'DGS10' if name=='fred' else 'NVDA')
            print(name+': VALID RESPONSE; account retrieval verified, not published')
        except ConnectorError as exc: print(str(exc))
if __name__=='__main__': main()
