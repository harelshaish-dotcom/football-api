import argparse

from database.connection import SessionLocal
from models.user import User


def promote_user(email: str) -> bool:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user is None:
            return False
        user.is_admin = True
        db.commit()
        return True
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a user to admin")
    parser.add_argument("email", help="Email address of the user to promote")
    args = parser.parse_args()

    if not promote_user(args.email):
        parser.error(f"No user found with email {args.email}")
    print(f"Promoted {args.email.lower()} to admin")


if __name__ == "__main__":
    main()