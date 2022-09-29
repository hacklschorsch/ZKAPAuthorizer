from typing import Any, Mapping

from attrs import define
from challenge_bypass_ristretto import (
    BatchDLEQProof,
    BlindedToken,
    PublicKey,
    SigningKey,
)
from twisted.internet.address import IPv4Address
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.interfaces import IListeningPort, IReactorTCP
from twisted.python.filepath import FilePath
from twisted.web.iweb import IRequest
from twisted.web.resource import Resource
from twisted.web.server import Site

from .._json import dumps_utf8, loads


@define
class Issuer:
    port: IListeningPort
    signing_key_path: FilePath

    # testresources jams crap onto us
    issuer_dir: Any = None

    @property
    def allowed_public_keys(self) -> list[PublicKey]:
        return [
            PublicKey.from_signing_key(
                SigningKey.decode_base64(self.signing_key_path.getContent())
            )
        ]

    @property
    def encoded_allowed_public_keys(self) -> str:
        return ",".join(
            k.encode_base64().decode("ascii") for k in self.allowed_public_keys
        )

    @property
    def root_url(self) -> str:
        address = self.port.getHost()
        assert isinstance(address, IPv4Address)
        return f"http://127.0.0.1:{address.port}/"

    @property
    def server_config(self) -> Mapping[str, str]:
        return {
            "ristretto-issuer-root-url": self.root_url,
            "ristretto-signing-key-path": self.signing_key_path.asTextMode().path,
        }

    @property
    def client_config(self) -> Mapping[str, str]:
        return {
            "redeemer": "ristretto",
            "ristretto-issuer-root-url": self.root_url,
            "allowed-public-keys": self.encoded_allowed_public_keys,
        }


class Redeem(Resource):
    def __init__(self, signing_key: SigningKey) -> None:
        Resource.__init__(self)
        self.signing_key = signing_key

    def render_POST(self, request: IRequest) -> bytes:
        # cattrs
        obj = loads(request.content.read())
        assert isinstance(obj, dict)
        tokens = obj["redeemTokens"]
        assert isinstance(tokens, list)

        blinded_tokens = [
            BlindedToken.decode_base64(blinded_token.encode("ascii"))
            for blinded_token in tokens
        ]

        signatures = list(
            self.signing_key.sign(blinded_token) for blinded_token in blinded_tokens
        )

        proof = BatchDLEQProof.create(
            self.signing_key,
            blinded_tokens,
            signatures,
        )
        return dumps_utf8(
            {
                "success": True,
                "signatures": [
                    sig.encode_base64().decode("ascii") for sig in signatures
                ],
                "proof": proof.encode_base64().decode("ascii"),
                "public-key": PublicKey.from_signing_key(self.signing_key)
                .encode_base64()
                .decode("ascii"),
            }
        )


def issuer(signing_key: SigningKey) -> Site:
    v1 = Resource()
    v1.putChild(b"redeem", Redeem(signing_key))

    r = Resource()
    r.putChild(b"v1", v1)

    return Site(r)


def run_issuer(reactor: IReactorTCP, signing_key_path: FilePath) -> Issuer:
    signing_key = SigningKey.decode_base64(signing_key_path.getContent())
    port = reactor.listenTCP(0, issuer(signing_key), backlog=3, interface="127.0.0.1")
    return Issuer(port, signing_key_path)


def stop_issuer(issuer: Issuer) -> Deferred[None]:
    return maybeDeferred(issuer.port.stopListening)  # type: ignore[arg-type]
