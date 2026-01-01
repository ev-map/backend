from evmap_backend.data_sources.nobil.parser import fix_city_capitalization


def test_fix_city_capitalization():
    # if not all-caps, return as is
    assert fix_city_capitalization("oslo") == "oslo"
    assert fix_city_capitalization("Oslo") == "Oslo"
    assert fix_city_capitalization("OSlo") == "OSlo"

    # if all-caps, fix capitalization
    assert fix_city_capitalization("OSLO") == "Oslo"
    assert fix_city_capitalization("TROMSØ") == "Tromsø"
    assert fix_city_capitalization("ØVRE ÅRDAL") == "Øvre Årdal"
    assert fix_city_capitalization("VANG PÅ HEDMARKEN") == "Vang på Hedmarken"
    assert fix_city_capitalization("MO I RANA") == "Mo i Rana"
    assert fix_city_capitalization("KRISTIANSAND S") == "Kristiansand S"
