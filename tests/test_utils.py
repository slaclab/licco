from dal.utils import diff_arrays

def test_arr_diff():
    old = ['a', 'b']
    new = ['b', 'c']
    diff = diff_arrays(old, new)

    assert diff.removed == ['a']
    assert diff.new == ['c']
    assert diff.in_both == ['b']
