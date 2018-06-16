from testtools import TestCase
from testtools.matchers import Equals, MatchesListwise

from fugue.test.util import depends_on


class DependsOnTests(TestCase):
    """
    Tests for `depends_on`.
    """
    class FakeTest(object):
        def __init__(self):
            self.skipped = []
            self.skipTest = self.skipped.append

        @depends_on('fugue', 'absolutely_not_a_thing')
        def test_missing(self):
            pass

        @depends_on('fugue')
        def test_exists(self):
            pass

    def test_missing(self):
        """
        If any dependency is missing, skip the test with a message.
        """
        test = self.FakeTest()
        test.test_missing()
        self.assertThat(
            test.skipped,
            MatchesListwise([
                Equals('"absolutely_not_a_thing" dependency missing')]))

    def test_exists(self):
        """
        If all dependencies are available, the test is not skipped.
        """
        test = self.FakeTest()
        test.test_exists()
        self.assertThat(test.skipped, Equals([]))
