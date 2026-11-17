import json
import pytest
from scripts.collect_lean import validated_result


def test_real_schema_and_order_event_array(tmp_path):
    (tmp_path/'a-order-events.json').write_text('[]')
    result={'state':{'Status':'Completed','RuntimeError':''},'statistics':{'Total Orders':'26'},'runtimeStatistics':{'Input observations':'1502'}}
    (tmp_path/'result.json').write_text(json.dumps(result))
    assert validated_result(tmp_path)['Statistics']['Total Orders']=='26'


def test_no_observations_is_not_a_success(tmp_path):
    (tmp_path/'result.json').write_text(json.dumps({'state':{'Status':'Completed'},'statistics':{'Total Orders':'0'},'runtimeStatistics':{'Input observations':'0'}}))
    with pytest.raises(RuntimeError):validated_result(tmp_path)


def test_runtime_error_never_becomes_operational(tmp_path):
    (tmp_path/'result.json').write_text(json.dumps({'state':{'Status':'Completed','RuntimeError':'failure'},'statistics':{'Total Orders':'26'},'runtimeStatistics':{'Input observations':'1502'}}))
    with pytest.raises(RuntimeError):validated_result(tmp_path)
