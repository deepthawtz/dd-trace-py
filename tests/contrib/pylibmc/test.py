
# stdlib
import time
from unittest.case import SkipTest

# 3p
import pylibmc
from nose.tools import eq_

# project
from ddtrace import Tracer
from ddtrace.ext import errors
from ddtrace.contrib.pylibmc import TracedClient
from tests.test_tracer import DummyWriter
from tests.contrib.config import MEMCACHED_CONFIG as cfg


TEST_SERVICE = "foobar"


class TestPylibmc(object):

    def test_upgrade(self):
        raise SkipTest("upgrade memcached")
        # add tests for touch, cas, gets etc

    def test_append_prepend(self):
        client, tracer = _setup()
        # test
        start = time.time()
        client.set("a", "crow")
        client.prepend("a", "holy ")
        client.append("a", "!")
        eq_(client.get("a"), "holy crow!")
        end = time.time()
        # verify spans
        spans = tracer.writer.pop()
        for s in spans:
            _verify_cache_span(s, start, end)
        expected_resources = sorted(["append", "prepend", "get", "set"])
        resources = sorted(s.resource for s in spans)
        eq_(expected_resources, resources)



    def test_incr_decr(self):
        client, tracer = _setup()
        # test
        start = time.time()
        client.set("a", 1)
        client.incr("a", 2)
        client.decr("a", 1)
        v = client.get("a")
        assert v == 2
        end = time.time()
        # verify spans
        spans = tracer.writer.pop()
        for s in spans:
            _verify_cache_span(s, start, end)
        expected_resources = sorted(["get", "set", "incr", "decr"])
        resources = sorted(s.resource for s in spans)
        eq_(expected_resources, resources)


    def test_clone(self):
        # ensure cloned connections are traced as well.
        client, tracer = _setup()
        cloned = client.clone()
        start = time.time()
        cloned.get("a")
        end = time.time()
        spans = tracer.writer.pop()
        for s in spans:
            _verify_cache_span(s, start, end)
        expected_resources = ["get"]
        resources = sorted(s.resource for s in spans)
        eq_(expected_resources, resources)

    def test_get_set_multi(self):
        client, tracer = _setup()
        # test
        start = time.time()
        client.set_multi({"a":1, "b":2})
        out = client.get_multi(["a", "c"])
        eq_(out, {"a":1})
        client.delete_multi(["a", "c"])
        end = time.time()
        # verify
        spans = tracer.writer.pop()
        for s in spans:
            _verify_cache_span(s, start, end)
        expected_resources = sorted(["get_multi", "set_multi", "delete_multi"])
        resources = sorted(s.resource for s in spans)
        eq_(expected_resources, resources)

    def test_get_set_delete(self):
        client, tracer = _setup()
        # test
        k = "key-foo"
        v = "val-foo"
        start = time.time()
        client.delete(k) # just in case
        out = client.get(k)
        assert out is None, out
        client.set(k, v)
        out = client.get(k)
        eq_(out, v)
        end = time.time()
        # verify
        spans = tracer.writer.pop()
        for s in spans:
            _verify_cache_span(s, start, end)
        expected_resources = sorted(["get", "get", "delete", "set"])
        resources = sorted(s.resource for s in spans)
        eq_(expected_resources, resources)

def _verify_cache_span(s, start, end):
    assert s.start > start
    assert s.start + s.duration < end
    eq_(s.service, TEST_SERVICE)
    eq_(s.span_type, "cache")
    eq_(s.name, "memcached.cmd")
    eq_(s.get_tag("out.host"), cfg["host"])
    eq_(s.get_tag("out.port"), str(cfg["port"]))



def _setup():
    url = "%s:%s" % (cfg["host"], cfg["port"])
    raw_client = pylibmc.Client([url])
    raw_client.flush_all()

    tracer = Tracer()
    tracer.writer = DummyWriter()

    client = TracedClient(raw_client, tracer, TEST_SERVICE)
    return client, tracer
