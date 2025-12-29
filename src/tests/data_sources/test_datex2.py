import datetime
from urllib.parse import quote_from_bytes

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from cryptography.x509.oid import NameOID
from cryptography.x509.verification import VerificationError
from django.http import HttpRequest

from evmap_backend.data_sources.datex2.source import BaseMobilithekDatex2DataSource


@pytest.fixture
def random_x509_certificate():
    key = generate_private_key(65537, 2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "ev-map.app")]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    random_certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("ev-map.app")]), critical=False
        )
        .add_extension(x509.BasicConstraints(False, None), critical=True)
        .add_extension(
            x509.KeyUsage(True, False, True, False, False, False, True, False, False),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [
                    x509.ExtendedKeyUsageOID.CLIENT_AUTH,
                    x509.ExtendedKeyUsageOID.SERVER_AUTH,
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return random_certificate


def test_verify_push_mobilithek(random_x509_certificate):
    class DummyMobilithekDatex2DataSource(BaseMobilithekDatex2DataSource):
        id = "dummy"
        subscription_id = "dummy"

    ds = DummyMobilithekDatex2DataSource()

    # no certificate
    req = HttpRequest()
    with pytest.raises(PermissionError):
        ds.verify_push(req)

    # unparseable certificate
    req = HttpRequest()
    req.META["HTTP_X_FORWARDED_CLIENT_CERT"] = "unparseable-cert"
    with pytest.raises(ValueError):
        ds.verify_push(req)

    # invalid certificate
    cert_header = quote_from_bytes(
        random_x509_certificate.public_bytes(encoding=serialization.Encoding.PEM)
    )
    req = HttpRequest()
    req.META["HTTP_X_FORWARDED_CLIENT_CERT"] = cert_header
    with pytest.raises(VerificationError):
        ds.verify_push(req)

    # valid certificate
    req = HttpRequest()
    req.META["HTTP_X_FORWARDED_CLIENT_CERT"] = (
        "-----BEGIN%20CERTIFICATE-----%0AMIIDyjCCArKgAwIBAgIUS6la6wLlULQEzDp8gittrRyVtoYwDQYJKoZIhvcNAQEL%0ABQAwFTETMBEGA1UEAwwKbTJtX2ludF9jYTAeFw0yNTA5MTAwNTE1NTJaFw0yNzA5%0AMTAwNTE2MjFaMBkxFzAVBgNVBAMTDm91dGdvaW5nY2VydC0yMIIBojANBgkqhkiG%0A9w0BAQEFAAOCAY8AMIIBigKCAYEAx1FemzgSxaOjYm%2BrBjOUb%2FqNEUO4SmPBw%2FtV%0Ab0vZRtekmAu9CLMpZLhWTmWljiCbpAsLVxyJ6s1Z1TKm3jFS%2Be2mj7yjQtZjwqP%2F%0AIkriTWDEy3NhOYy44%2Bn%2Fi3wEdIQQTEErPE4QjlA5cxBkhZWDfe0pDgxTOlibtSew%0ANbI35ar1rWO5hBoGPsw34skWj3%2B%2Fn7pnrh4yJhg2sGTA%2B%2FI5aUz1Sku4YAyRzWqu%0AXP%2FJ2GqLrqkRgXJMpvc1qwpyPfnO9d2DU8wYjtjvMVjGv3flEgrUsa17CUHq%2BvO0%0A2%2BJmR6ovjG%2F7QzW3VWbEbBeu4li94J3l0ipY0618L0TuFCkqtpMbktD8o5isJPu2%0AE9FMosnxbm9%2BVyvTnw6QoSZTmqnlxsQHo%2BRVre%2BRDrVwwHIx8UIWJ7he3YxzDarl%0AKRQXk8nxtFbjHcHDBMHFWUKekficKPwlrDDfu5DTiZIXqT4VC7nhzhOqeiK7mT%2Fn%0AuepiWBtueetrHsQMwxSwoB6JYnc5AgMBAAGjgY0wgYowDgYDVR0PAQH%2FBAQDAgOo%0AMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAdBgNVHQ4EFgQUBSicGnrt%0AJddT78JazPMIb4asHYcwHwYDVR0jBBgwFoAUqrU%2FtDEChRjVQXyhfPj3%2B%2F9fCiMw%0AGQYDVR0RBBIwEIIOb3V0Z29pbmdjZXJ0LTIwDQYJKoZIhvcNAQELBQADggEBAFsY%0Akz1l6EHoVI%2FpwNZeC0DNa7N78TFwkFIzHLUs46FeSEwD0Wpo0OjDmxbpgaCVZ7Od%0Ag%2FSBHdN4qNV9L0IG0Mp8Ax%2Fdi%2Buify2kiGNPizFWUzqzuprZZ8u2oQTYiMsXG0yd%0A8BdT8afECaNeM6g4oC%2Fvc1Q%2BnaARA%2BhGTTPEGEHBNGhoeeVbnge3AVWQxTigSz5k%0AVhAVSGpM0Wh2th1AdJZ0Vk1lEbp2U5n7C3m%2BFPI4mDcARh%2F2GhPpC1XRAYECTTbp%0A67DaTZZyJlec0GStSTJcIOqTGD3pfo3dcJzGLcb74De57n%2BacMrBAXu50bjtloYv%0Aefi8HTk316yTHLex31U%3D%0A-----END%20CERTIFICATE-----%0A"
    )
    ds.verify_push(req)
