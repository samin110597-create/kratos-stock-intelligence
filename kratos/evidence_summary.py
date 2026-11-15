"""Only verbatim supplied evidence may leave the experimental model endpoint."""
import json

def verified_extract(response, evidence):
    try:
        text=response.strip()
        if text.startswith('```'):
            text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
        items=json.loads(text)
        if not isinstance(items,list) or not 1<=len(items)<=4:
            raise ValueError('Invalid selection')
        if any(not isinstance(item,str) or len(item.strip())<4 or item not in evidence for item in items):
            raise ValueError('Unsupported statement')
        return 'Model-selected excerpts from supplied evidence (not independently verified):\n\n'+'\n'.join('- '+item for item in dict.fromkeys(items))
    except (ValueError,TypeError):
        return 'The model did not return a verifiable extract. No generated interpretation is shown; use the original evidence.'
