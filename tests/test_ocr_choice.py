from blacklist_detect.ocr_engine import choose_name_read


def test_agreement_keeps_the_surer_spelling():
    chosen = choose_name_read(("无害虎皮...", 0.91), ("无害虎皮", 0.99))
    assert chosen[0] == "无害虎皮"


def test_a_small_edge_does_not_replace_the_primary_read():
    chosen = choose_name_read(("栀盏灯下", 0.97), ("栀盖灯下", 0.99))
    assert chosen[0] == "栀盏灯下"


def test_a_clearly_surer_alternate_replaces_a_weak_read():
    chosen = choose_name_read(("穷", 0.40), ("穷不知", 0.96))
    assert chosen == ("穷不知", 0.96)
