from sscutils.utils import format_code


def test_lint():
    bad_c = "x = 10"
    good_c = "x =  10"
    assert good_c == format_code(bad_c)
    assert good_c == format_code(good_c)
