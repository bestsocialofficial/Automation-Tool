"""
manage_users.py

Create and manage dashboard login accounts (stored in MongoDB, seo.users).

Usage:
    python manage_users.py add <username> --domains domain1.com domain2.com
    python manage_users.py add <username> --admin
    python manage_users.py list
    python manage_users.py password <username>
    python manage_users.py remove <username>

Access rules:
    --admin, or a user with no --domains, sees every domain in the data.
    A user with --domains only sees those domains on the dashboard.

Passwords are prompted for interactively (nothing is echoed). The --password
flag exists for scripting but leaves the password in your shell history —
avoid it for real accounts.
"""

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

from auth_utils import hash_password

load_dotenv()


def users_collection():
    # Connection defaults must match dashboard.mongo_settings().
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGO_DB", "seo")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    coll = client[db_name]["users"]
    coll.create_index("username", unique=True)
    return coll


def read_password(args):
    if getattr(args, "password", None):
        return args.password
    pw = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        sys.exit("Passwords do not match.")
    if len(pw) < 6:
        sys.exit("Use at least 6 characters.")
    return pw


def cmd_add(args):
    coll = users_collection()
    username = args.username.strip().lower()
    if coll.find_one({"username": username}):
        sys.exit(f"User {username!r} already exists. Use 'password' to reset it.")

    password = read_password(args)
    salt, digest = hash_password(password)
    coll.insert_one(
        {
            "username": username,
            "salt": salt,
            "password_hash": digest,
            "is_admin": bool(args.admin),
            "domains": args.domains or [],
            "created_at": datetime.now(timezone.utc),
        }
    )
    scope = (
        "all domains (admin)"
        if args.admin
        else ", ".join(args.domains) if args.domains else "all domains"
    )
    print(f"Created user {username!r} with access to: {scope}")


def cmd_list(args):
    coll = users_collection()
    users = list(coll.find().sort("username"))
    if not users:
        print("No users yet. Create one with: python manage_users.py add <name>")
        return
    for u in users:
        scope = "ADMIN" if u.get("is_admin") else (", ".join(u.get("domains") or []) or "all domains")
        print(f"  {u['username']:<20} {scope}")


def cmd_password(args):
    coll = users_collection()
    username = args.username.strip().lower()
    if not coll.find_one({"username": username}):
        sys.exit(f"No user named {username!r}.")
    password = read_password(args)
    salt, digest = hash_password(password)
    coll.update_one(
        {"username": username},
        {"$set": {"salt": salt, "password_hash": digest}},
    )
    print(f"Password updated for {username!r}.")


def cmd_remove(args):
    coll = users_collection()
    username = args.username.strip().lower()
    result = coll.delete_one({"username": username})
    if result.deleted_count:
        print(f"Removed user {username!r}.")
    else:
        sys.exit(f"No user named {username!r}.")


def main():
    parser = argparse.ArgumentParser(description="Manage dashboard login accounts")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Create a new user")
    p_add.add_argument("username")
    p_add.add_argument("--domains", nargs="*", help="Domains this user may see")
    p_add.add_argument("--admin", action="store_true", help="Full access to all domains")
    p_add.add_argument("--password", help="Set password non-interactively (avoid for real accounts)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List users")
    p_list.set_defaults(func=cmd_list)

    p_pw = sub.add_parser("password", help="Reset a user's password")
    p_pw.add_argument("username")
    p_pw.add_argument("--password", help="Set password non-interactively")
    p_pw.set_defaults(func=cmd_password)

    p_rm = sub.add_parser("remove", help="Delete a user")
    p_rm.add_argument("username")
    p_rm.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
