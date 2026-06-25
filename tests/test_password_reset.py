from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.auth import login_access_token, request_password_reset_code, reset_password_with_code
from app.schemas.schemas import PasswordResetRequest, PasswordResetVerify
from app.core.security import get_password_hash, verify_password
from app.db.session import Base
from app.models.models import User


class PasswordResetFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.temp_db.close()
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.db = self.SessionLocal()
        self.db.add(
            User(
                email="reset@example.com",
                hashed_password=get_password_hash("OldPassword1234"),
                full_name="Reset User",
                is_active=True,
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_request_and_reset_password(self) -> None:
        request_result = request_password_reset_code(
            db=self.db,
            payload=PasswordResetRequest(email="reset@example.com"),
        )
        self.assertIn("reset_id", request_result)
        self.assertIsNotNone(request_result["debug_code"])

        reset_result = reset_password_with_code(
            db=self.db,
            payload=PasswordResetVerify(
                reset_id=request_result["reset_id"],
                code=request_result["debug_code"],
                new_password="NewPassword1234",
            ),
        )
        self.assertEqual(reset_result["message"], "Mot de passe modifie avec succes.")

        updated_user = self.db.query(User).filter(User.email == "reset@example.com").first()
        self.assertIsNotNone(updated_user)
        assert updated_user is not None
        self.assertTrue(verify_password("NewPassword1234", updated_user.hashed_password))
        self.assertFalse(verify_password("OldPassword1234", updated_user.hashed_password))

        login_result = login_access_token(
            db=self.db,
            form_data=SimpleNamespace(username="reset@example.com", password="NewPassword1234"),
        )
        self.assertIn("access_token", login_result)


if __name__ == "__main__":
    unittest.main()
