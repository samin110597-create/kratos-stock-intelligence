from kratos.evidence_summary import verified_extract

def test_model_may_only_copy_evidence():
    evidence='Daily trend is DOWN. Weekly trend is MIXED.'
    assert 'Daily trend is DOWN.' in verified_extract('["Daily trend is DOWN."]',evidence)
    for generated in ('["Sentiment is negative."]','["Price will reach 200."]','["Daily trend is UP."]','not json','{}','[]'):
        assert 'No generated interpretation' in verified_extract(generated,evidence)
