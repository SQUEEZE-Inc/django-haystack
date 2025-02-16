import datetime

from django.contrib.gis.measure import D
from django.test import TestCase

from haystack import connections
from haystack.inputs import Exact
from haystack.models import SearchResult
from haystack.query import SQ, SearchQuerySet

from ..core.models import AnotherMockModel, MockModel


class Elasticsearch5SearchQueryTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.sq = connections["elasticsearch"].get_query()

    def test_build_query_all(self):
        self.assertEqual(self.sq.build_query(), "*:*")

    def test_build_query_single_word(self):
        self.sq.add_filter(SQ(content="hello"))
        self.assertEqual(self.sq.build_query(), "(hello)")

    def test_build_query_boolean(self):
        self.sq.add_filter(SQ(content=True))
        self.assertEqual(self.sq.build_query(), "(True)")

    def test_regression_slash_search(self):
        self.sq.add_filter(SQ(content="hello/"))
        self.assertEqual(self.sq.build_query(), "(hello\\/)")

    def test_build_query_datetime(self):
        self.sq.add_filter(SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertEqual(self.sq.build_query(), "(2009-05-08T11:28:00)")

    def test_build_query_multiple_words_and(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_filter(SQ(content="world"))
        self.assertEqual(self.sq.build_query(), "((hello) AND (world))")

    def test_build_query_multiple_words_not(self):
        self.sq.add_filter(~SQ(content="hello"))
        self.sq.add_filter(~SQ(content="world"))
        self.assertEqual(self.sq.build_query(), "(NOT ((hello)) AND NOT ((world)))")

    def test_build_query_multiple_words_or(self):
        self.sq.add_filter(~SQ(content="hello"))
        self.sq.add_filter(SQ(content="hello"), use_or=True)
        self.assertEqual(self.sq.build_query(), "(NOT ((hello)) OR (hello))")

    def test_build_query_multiple_words_mixed(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(content="hello"), use_or=True)
        self.sq.add_filter(~SQ(content="world"))
        self.assertEqual(
            self.sq.build_query(), "(((why) OR (hello)) AND NOT ((world)))"
        )

    def test_build_query_phrase(self):
        self.sq.add_filter(SQ(content="hello world"))
        self.assertEqual(self.sq.build_query(), "(hello AND world)")

        self.sq.add_filter(SQ(content__exact="hello world"))
        self.assertEqual(
            self.sq.build_query(), '((hello AND world) AND ("hello world"))'
        )

    def test_build_query_boost(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_boost("world", 5)
        self.assertEqual(self.sq.build_query(), "(hello) world^5")

    def test_build_query_multiple_filter_types(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(pub_date__lte=Exact("2009-02-10 01:59:00")))
        self.sq.add_filter(SQ(author__gt="daniel"))
        self.sq.add_filter(SQ(created__lt=Exact("2009-02-12 12:13:00")))
        self.sq.add_filter(SQ(title__gte="B"))
        self.sq.add_filter(SQ(id__in=[1, 2, 3]))
        self.sq.add_filter(SQ(rating__range=[3, 5]))
        self.assertEqual(
            self.sq.build_query(),
            '((why) AND pub_date:([* TO "2009-02-10 01:59:00"]) AND author:({"daniel" TO *}) AND created:({* TO "2009-02-12 12:13:00"}) AND title:(["B" TO *]) AND id:("1" OR "2" OR "3") AND rating:(["3" TO "5"]))',
        )

    def test_build_query_multiple_filter_types_with_datetimes(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(pub_date__lte=datetime.datetime(2009, 2, 10, 1, 59, 0)))
        self.sq.add_filter(SQ(author__gt="daniel"))
        self.sq.add_filter(SQ(created__lt=datetime.datetime(2009, 2, 12, 12, 13, 0)))
        self.sq.add_filter(SQ(title__gte="B"))
        self.sq.add_filter(SQ(id__in=[1, 2, 3]))
        self.sq.add_filter(SQ(rating__range=[3, 5]))
        self.assertEqual(
            self.sq.build_query(),
            '((why) AND pub_date:([* TO "2009-02-10T01:59:00"]) AND author:({"daniel" TO *}) AND created:({* TO "2009-02-12T12:13:00"}) AND title:(["B" TO *]) AND id:("1" OR "2" OR "3") AND rating:(["3" TO "5"]))',
        )

    def test_build_query_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertEqual(
            self.sq.build_query(),
            '((why) AND title:("A Famous Paper" OR "An Infamous Article"))',
        )

    def test_build_query_in_filter_datetime(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(pub_date__in=[datetime.datetime(2009, 7, 6, 1, 56, 21)]))
        self.assertEqual(
            self.sq.build_query(), '((why) AND pub_date:("2009-07-06T01:56:21"))'
        )

    def test_build_query_in_with_set(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__in={"A Famous Paper", "An Infamous Article"}))
        self.assertTrue("((why) AND title:(" in self.sq.build_query())
        self.assertTrue('"A Famous Paper"' in self.sq.build_query())
        self.assertTrue('"An Infamous Article"' in self.sq.build_query())

    def test_build_query_wildcard_filter_types(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__startswith="haystack"))
        self.assertEqual(self.sq.build_query(), "((why) AND title:(haystack*))")

    def test_build_query_fuzzy_filter_types(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__fuzzy="haystack"))
        self.assertEqual(self.sq.build_query(), "((why) AND title:(haystack~))")

    def test_clean(self):
        self.assertEqual(self.sq.clean("hello world"), "hello world")
        self.assertEqual(self.sq.clean("hello AND world"), "hello and world")
        self.assertEqual(
            self.sq.clean(
                r'hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \ / world'
            ),
            'hello and or not to \\+ \\- \\&& \\|| \\! \\( \\) \\{ \\} \\[ \\] \\^ \\" \\~ \\* \\? \\: \\\\ \\/ world',
        )
        self.assertEqual(
            self.sq.clean("so please NOTe i am in a bAND and bORed"),
            "so please NOTe i am in a bAND and bORed",
        )

    def test_build_query_with_models(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_model(MockModel)
        self.assertEqual(self.sq.build_query(), "(hello)")

        self.sq.add_model(AnotherMockModel)
        self.assertEqual(self.sq.build_query(), "(hello)")

    def test_set_result_class(self):
        # Assert that we're defaulting to ``SearchResult``.
        self.assertTrue(issubclass(self.sq.result_class, SearchResult))

        # Custom class.
        class IttyBittyResult(object):
            pass

        self.sq.set_result_class(IttyBittyResult)
        self.assertTrue(issubclass(self.sq.result_class, IttyBittyResult))

        # Reset to default.
        self.sq.set_result_class(None)
        self.assertTrue(issubclass(self.sq.result_class, SearchResult))

    def test_in_filter_values_list(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__in=[1, 2, 3]))
        self.assertEqual(self.sq.build_query(), '((why) AND title:("1" OR "2" OR "3"))')

    def test_narrow_sq(self):
        sqs = SearchQuerySet(using="elasticsearch").narrow(SQ(foo="moof"))
        self.assertTrue(isinstance(sqs, SearchQuerySet))
        self.assertEqual(len(sqs.query.narrow_queries), 1)
        self.assertEqual(sqs.query.narrow_queries.pop(), "foo:(moof)")

    def test_build_query_with_dwithin_range(self):
        from django.contrib.gis.geos import Point

        backend = connections["elasticsearch"].get_backend()
        search_kwargs = backend.build_search_kwargs(
            "where",
            dwithin={
                "field": "location_field",
                "point": Point(1.2345678, 2.3456789),
                "distance": D(m=500),
            },
        )
        self.assertEqual(
            search_kwargs["query"]["bool"]["filter"]["bool"]["must"][1]["geo_distance"],
            {
                "distance": "0.500000km",
                "location_field": {"lat": 2.3456789, "lon": 1.2345678},
            },
        )
