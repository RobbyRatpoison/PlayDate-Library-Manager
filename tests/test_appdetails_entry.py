from scrapers import appdetails_entry


def test_keyed_by_requested_appid():
    d = {"10": {"success": True, "data": {"steam_appid": 10}}}
    assert appdetails_entry(d, 10) is d["10"]


def test_falls_back_to_entry_with_matching_steam_appid():
    # Cloudbuilt: asked for 262390, Steam answered under its DLC's key
    d = {"307550": {"success": True, "data": {"steam_appid": 262390}}}
    assert appdetails_entry(d, 262390) is d["307550"]


def test_no_match_is_empty():
    d = {"307550": {"success": True, "data": {"steam_appid": 307550}}}
    assert appdetails_entry(d, 262390) == {}
    assert appdetails_entry(None, 1) == {}
