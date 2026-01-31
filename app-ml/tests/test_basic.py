"""
Basic test to verify testing framework setup.
"""


def test_basic_assertion():
    """Test basic assertion."""
    assert 1 + 1 == 2


def test_string_operations():
    """Test string operations."""
    s = "hello world"
    assert "hello" in s
    assert s.upper() == "HELLO WORLD"
    assert len(s) == 11


def test_list_operations():
    """Test list operations."""
    lst = [1, 2, 3, 4, 5]
    assert len(lst) == 5
    assert sum(lst) == 15
    assert max(lst) == 5
    assert min(lst) == 1


def test_dict_operations():
    """Test dictionary operations."""
    d = {"key": "value", "number": 42}
    assert d["key"] == "value"
    assert d["number"] == 42
    assert "key" in d
    assert len(d) == 2


class TestBasicClass:
    """Basic test class."""

    def test_class_method(self):
        """Test class method."""
        self.value = 10
        assert self.value == 10

    def test_math_operations(self):
        """Test math operations."""
        result = (5 * 3) + 2
        assert result == 17
        assert result > 10
        assert result < 20
