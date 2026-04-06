import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from jose import jwt
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, get_password_hash, verify_password
from app.schemas.schemas import BookingCreate, ListingCreate, RegisterCodeRequest, RegisterCodeVerify, ReviewCreate, UserCreate
from app.services.google_auth import GoogleTokenError, verify_google_id_token


class SecurityAndSchemaTests(unittest.TestCase):
    def test_password_hash_roundtrip(self) -> None:
        password = "CorrectHorseBatteryStaple123!"
        hashed = get_password_hash(password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_long_password_supported(self) -> None:
        password = "A" * 200
        hashed = get_password_hash(password)
        self.assertTrue(verify_password(password, hashed))

    def test_user_create_forbids_role_override(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate.model_validate(
                {
                    "email": "test@example.com",
                    "password": "Password1234",
                    "role": "admin",
                }
            )

    def test_listing_type_must_be_known_enum(self) -> None:
        with self.assertRaises(ValidationError):
            ListingCreate.model_validate(
                {
                    "title": "Invalid listing",
                    "type": "unknown-type",
                    "location": "Alger",
                    "price": 1000,
                }
            )

    def test_access_token_contains_subject(self) -> None:
        token = create_access_token("test@example.com", expires_delta=timedelta(minutes=10))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(payload.get("sub"), "test@example.com")

    def test_review_rating_validation(self) -> None:
        with self.assertRaises(ValidationError):
            ReviewCreate(listing_id=1, rating=6, comment="Invalid rating")

    def test_listing_availability_dates_format_validation(self) -> None:
        with self.assertRaises(ValidationError):
            ListingCreate.model_validate(
                {
                    "title": "Studio test",
                    "type": "immobilier",
                    "location": "Alger",
                    "price": 12000,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "area": 35,
                    "availability_dates": "2026/01/01,2026-01-02",
                }
            )

    def test_hotel_listing_allows_missing_area(self) -> None:
        payload = ListingCreate.model_validate(
            {
                "title": "Hotel test",
                "type": "immobilier",
                "category": "hotel",
                "location": "Oran",
                "price": 18000,
                "bedrooms": 8,
                "bathrooms": 5,
            }
        )
        self.assertIsNone(payload.area)

    def test_booking_date_range_validation(self) -> None:
        with self.assertRaises(ValidationError):
            BookingCreate.model_validate(
                {
                    "listing_id": 1,
                    "start_date": datetime(2026, 2, 10, 12, 0, 0),
                    "end_date": datetime(2026, 2, 10, 12, 0, 0),
                }
            )

    def test_booking_rooms_reserved_must_be_positive(self) -> None:
        with self.assertRaises(ValidationError):
            BookingCreate.model_validate(
                {
                    "listing_id": 1,
                    "start_date": datetime(2026, 2, 10, 12, 0, 0),
                    "end_date": datetime(2026, 2, 12, 12, 0, 0),
                    "rooms_reserved": 0,
                }
            )

    def test_register_code_request_requires_phone_for_phone_channel(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterCodeRequest.model_validate(
                {
                    "email": "otp@example.com",
                    "password": "Password1234",
                    "channel": "phone",
                }
            )

    def test_register_code_request_requires_email_for_email_channel(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterCodeRequest.model_validate(
                {
                    "phone_number": "+213551234567",
                    "password": "Password1234",
                    "channel": "email",
                }
            )

    def test_register_code_request_requires_phone_for_email_channel(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterCodeRequest.model_validate(
                {
                    "email": "otp@example.com",
                    "password": "Password1234",
                    "channel": "email",
                }
            )

    def test_register_code_request_allows_phone_channel_without_email(self) -> None:
        payload = RegisterCodeRequest.model_validate(
            {
                "phone_number": "+213551234567",
                "password": "Password1234",
                "channel": "phone",
            }
        )
        self.assertIsNone(payload.email)
        self.assertEqual(payload.phone_number, "+213551234567")

    def test_register_code_verify_must_be_numeric(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterCodeVerify.model_validate(
                {
                    "verification_id": 1,
                    "code": "12ab56",
                }
            )

    @patch("app.services.google_auth._verify_token_signature")
    @patch("app.services.google_auth._get_google_key", return_value={"kty": "RSA", "kid": "key-1"})
    @patch("app.services.google_auth.jwt.get_unverified_claims")
    @patch("app.services.google_auth.jwt.get_unverified_header")
    def test_google_id_token_validation_success(
        self,
        mocked_header,
        mocked_claims,
        _mocked_key,
        _mocked_signature,
    ) -> None:
        mocked_header.return_value = {"alg": "RS256", "kid": "key-1"}
        mocked_claims.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id",
            "exp": 4_102_444_800,  # 2100-01-01
            "email": "user@example.com",
            "email_verified": True,
            "sub": "google-user-123",
        }

        claims = verify_google_id_token("header.payload.signature", "google-client-id")
        self.assertEqual(claims["email"], "user@example.com")

    @patch("app.services.google_auth._verify_token_signature")
    @patch("app.services.google_auth._get_google_key", return_value={"kty": "RSA", "kid": "key-1"})
    @patch("app.services.google_auth.jwt.get_unverified_claims")
    @patch("app.services.google_auth.jwt.get_unverified_header")
    def test_google_id_token_validation_rejects_wrong_audience(
        self,
        mocked_header,
        mocked_claims,
        _mocked_key,
        _mocked_signature,
    ) -> None:
        mocked_header.return_value = {"alg": "RS256", "kid": "key-1"}
        mocked_claims.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "another-client-id",
            "exp": 4_102_444_800,  # 2100-01-01
            "email": "user@example.com",
            "email_verified": True,
            "sub": "google-user-123",
        }

        with self.assertRaises(GoogleTokenError):
            verify_google_id_token("header.payload.signature", "google-client-id")


if __name__ == "__main__":
    unittest.main()
