# Copyright 2019 PrivateStorage.io, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for Foolscap-related test helpers.
"""

from fixtures import Fixture
from typing import Optional, cast
from foolscap.api import Any, RemoteInterface, Violation  # type: ignore[attr-defined]
from foolscap.furl import decode_furl
from foolscap.pb import Tub
from foolscap.referenceable import RemoteReference, RemoteReferenceOnly, RemoteReferenceTracker
from hypothesis import given
from hypothesis.strategies import just, one_of
from testtools import TestCase
from testtools.matchers import (
    AfterPreprocessing,
    Always,
    Equals,
    IsInstance,
    MatchesAll,
)
from testtools.twistedsupport import failed, succeeded
from twisted.internet.defer import Deferred
from twisted.trial.unittest import TestCase as TrialTestCase

from ..foolscap import ShareStat
from .foolscap import BrokenCopyable, DummyReferenceable, Echoer, LocalRemote, RIStub
from .common import async_test

class IHasSchema(RemoteInterface):
    def method(arg=int):  # type: ignore[assignment,no-untyped-def]
        return bytes

    def good_method(arg=int):  # type: ignore[assignment,no-untyped-def]
        return None

    def whatever_method(arg=Any()): # type: ignore[no-untyped-def]
        return Any()


def remote_reference() -> RemoteReferenceOnly:
    tub = Tub()
    tub.setLocation("127.0.0.1:12345")
    url = tub.buildURL("efgh")

    # Ugh ugh ugh.  Skip over the extra correctness checking in
    # RemoteReferenceTracker.__init__ that requires having a broker by passing
    # the url as None and setting it after.
    tracker = RemoteReferenceTracker(None, None, None, RIStub)
    tracker.url = url

    ref = RemoteReferenceOnly(tracker)
    return ref


class LocalRemoteTests(TestCase):
    """
    Tests for the ``LocalRemote`` test double.
    """

    @given(
        ref=one_of(
            just(remote_reference()),
            just(LocalRemote(DummyReferenceable(RIStub))),
        ),
    )
    def test_tracker_url(self, ref: RemoteReference) -> None:
        """
        The URL of a remote reference can be retrieved using the tracker
        attribute.
        """
        self.assertThat(
            ref.tracker.getURL(),
            MatchesAll(
                IsInstance(str),
                AfterPreprocessing(
                    decode_furl,
                    Always(),
                ),
            ),
        )

    def test_arg_schema(self) -> None:
        """
        ``LocalRemote.callRemote`` returns a ``Deferred`` that fails with a
        ``Violation`` if an parameter receives an argument which doesn't
        conform to its schema.
        """
        ref = LocalRemote(DummyReferenceable(IHasSchema))
        self.assertThat(
            ref.callRemote("method", None),
            failed(
                AfterPreprocessing(
                    lambda f: f.type,
                    Equals(Violation),
                ),
            ),
        )

    def test_result_schema(self) -> None:
        """
        ``LocalRemote.callRemote`` returns a ``Deferred`` that fails with a
        ``Violation`` if a method returns an object which doesn't conform to
        the method's result schema.
        """
        ref = LocalRemote(DummyReferenceable(IHasSchema))
        self.assertThat(
            ref.callRemote("method", 0),
            failed(
                AfterPreprocessing(
                    lambda f: f.type,
                    Equals(Violation),
                ),
            ),
        )

    def test_successful_method(self) -> None:
        """
        ``LocalRemote.callRemote`` returns a ``Deferred`` that fires with the
        remote method's result if the arguments and result conform to their
        respective schemas.
        """
        ref = LocalRemote(DummyReferenceable(IHasSchema))
        self.assertThat(
            ref.callRemote("good_method", 0),
            succeeded(Equals(None)),
        )

    def test_argument_serialization_failure(self) -> None:
        """
        ``LocalRemote.callRemote`` returns a ``Deferred`` that fires with a
        failure if an argument cannot be serialized.
        """
        ref = LocalRemote(DummyReferenceable(IHasSchema))
        self.assertThat(
            ref.callRemote("whatever_method", BrokenCopyable()),
            failed(Always()),
        )

    def test_result_serialization_failure(self) -> None:
        """
        ``LocalRemote.callRemote`` returns a ``Deferred`` that fires with a
        failure if the method's result cannot be serialized.
        """

        class BrokenResultReferenceable(DummyReferenceable):
            def doRemoteCall(self, *a: object, **kw: object) -> BrokenCopyable:
                return BrokenCopyable()

        ref = LocalRemote(BrokenResultReferenceable(IHasSchema))
        self.assertThat(
            ref.callRemote("whatever_method", None),
            failed(Always()),
        )


class EchoerFixture(Fixture):
    tub: Tub
    furl: bytes

    def __init__(self) -> None:
        self.tub = Tub()
        self.tub.setLocation(b"tcp:0")

    def _setUp(self) -> None:
        self.tub.startService()
        self.furl = self.tub.registerReference(Echoer())

    def _cleanUp(self) -> Optional[Deferred[object]]:
        return cast(Optional[Deferred[object]], self.tub.stopService())


class SerializationTests(TrialTestCase):
    """
    Tests for the serialization of types used in the Foolscap API.
    """

    @async_test
    async def test_sharestat(self) -> None:
        """
        A ``ShareStat`` instance can be sent as an argument to and received in a
        response from a Foolscap remote method call.
        """
        await self._roundtrip_test(ShareStat(1, 2))

    async def _roundtrip_test(self, obj: object) -> None:
        """
        Send ``obj`` over Foolscap and receive it back again, equal to itself.
        """
        # So sad.  No Deferred support in testtools.TestCase or
        # fixture.Fixture, no fixture support in
        # twisted.trial.unittest.TestCase.
        fx = EchoerFixture()
        fx.setUp()
        self.addCleanup(fx._cleanUp)
        echoer = await fx.tub.getReference(fx.furl)
        received = await echoer.callRemote("echo", obj)
        self.assertEqual(obj, received)
