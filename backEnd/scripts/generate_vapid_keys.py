"""Generate VAPID keys for standards-based browser Web Push.

Run: python -m scripts.generate_vapid_keys
Copy the printed values into your secret manager or untracked .env file.
Never commit the private key.
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_scalar = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_point = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    print("# Store VAPID_PRIVATE_KEY as a secret; do not commit it.")
    print(f"VAPID_PUBLIC_KEY={b64url(public_point)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_scalar)}")
    print("VAPID_CLAIMS_EMAIL=mailto:admin@your-domain.example")


if __name__ == "__main__":
    main()
