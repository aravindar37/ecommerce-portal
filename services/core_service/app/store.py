"""Core Service repository — MongoDB Atlas primary with file-backed fallback."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.database import mongo
from app.config import CoreServiceSettings, settings
from app.ingestion.pipeline import run_ingestion

Json = dict[str, Any]


class StoreError(Exception):
    """Raised when repository operations fail."""


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def clone(value: Any) -> Any:
    return copy.deepcopy(value)


def new_id() -> str:
    return uuid.uuid4().hex[:24]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone_number(phone_number: str) -> str:
    """Normalize an already E.164-validated phone number."""

    return phone_number.strip()


def hash_password(password: str, salt: str | None = None) -> str:
    if settings.password_hash_algorithm == "argon2id" and salt is None:
        try:
            from argon2 import PasswordHasher
        except ImportError as exc:
            raise RuntimeError("argon2-cffi must be installed when PASSWORD_HASH_ALGORITHM=argon2id") from exc
        return f"argon2id${PasswordHasher().hash(password)}"
    chosen_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), chosen_salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${chosen_salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("argon2id$"):
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerificationError
        except ImportError as exc:
            raise RuntimeError("argon2-cffi must be installed to verify Argon2id password hashes") from exc
        try:
            return PasswordHasher().verify(password_hash.removeprefix("argon2id$"), password)
        except VerificationError:
            return False
    parts = password_hash.split("$")
    if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
        return False
    expected = hash_password(password, parts[1])
    return hmac.compare_digest(expected, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def default_state() -> Json:
    return {
        "users": [],
        "sessions": [],
        "products": [],
        "carts": [],
        "orders": [],
        "returnRequests": [],
        "supportTickets": [],
        "passwordResetTokens": [],
        "userActivityEvents": [],
        "agentToolAuditLogs": [],
        "ingestionStatus": {},
        "embeddingStatus": {},
        "counters": {"order": 0, "return": 0, "ticket": 0},
    }


# Collections that hold transactional data cleared on reset
_TRANSACTIONAL_COLLECTIONS = [
    "users",
    "sessions",
    "passwordResetTokens",
    "carts",
    "orders",
    "returnRequests",
    "supportTickets",
    "userActivityEvents",
    "agentToolAuditLogs",
    "counters",
]


class CoreStore:
    """MongoDB-primary repository with file-backed fallback for local dev without Atlas."""

    def __init__(self, config: CoreServiceSettings) -> None:
        self.config = config
        self.path = config.core_data_path
        self.state: Json = default_state()
        self.load()

    # ── File-backed helpers ──────────────────────────────────────────────────

    def load(self) -> None:
        if not self.path.exists():
            self.state = default_state()
            return
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Unable to load Core Service state from {self.path}: {exc}") from exc

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StoreError(f"Unable to save Core Service state to {self.path}: {exc}") from exc

    # ── MongoDB helpers ──────────────────────────────────────────────────────

    def mongo_collection(self, name: str) -> Any:
        try:
            return mongo.collection(name)
        except Exception as exc:
            raise StoreError(f"MongoDB collection '{name}' is unavailable: {exc}") from exc

    def normalize_mongo_record(self, record: Json | None) -> Json | None:
        if not isinstance(record, dict):
            return None
        normalized = clone(record)
        if "_id" in normalized:
            normalized["_id"] = str(normalized["_id"])
        return normalized

    def _docs(self, cursor: Any) -> list[Json]:
        """Convert a pymongo cursor to a list of normalized dicts."""
        return [self.normalize_mongo_record(doc) for doc in cursor if isinstance(doc, dict)]  # type: ignore[misc]

    # ── Reset and seed ───────────────────────────────────────────────────────

    def reset(self) -> None:
        if mongo.configured:
            for name in _TRANSACTIONAL_COLLECTIONS:
                self.mongo_collection(name).delete_many({})
        self.state = default_state()
        if not mongo.configured:
            self.save()

    def seed(self, products: str | None, users: bool, orders: bool, embeddings: bool) -> None:
        if users:
            self.seed_admin_user()
        if products:
            limit = 25 if products == "fashion-minimal" else None
            self.seed_products(limit)
        if embeddings:
            embedding_status = {
                "provider": self.config.embedding_provider,
                "model": self.config.embedding_model,
                "dimensions": self.config.embedding_dimensions,
                "textTemplateVersion": self.config.embedding_text_template_version,
                "vectorIndexName": self.config.mongodb_vector_index_name,
                "count": len(self.state["products"]),
            }
            self.state["embeddingStatus"] = embedding_status
            if mongo.configured:
                self.mongo_collection("serviceMetadata").replace_one(
                    {"_id": "embeddingStatus"}, {"_id": "embeddingStatus", "data": embedding_status}, upsert=True
                )
        if orders and self.state["products"] and (self.state["users"] or mongo.configured):
            self.seed_support_audit_log()
        if not mongo.configured:
            self.save()

    def seed_admin_user(self) -> None:
        email = normalize_email(self.config.admin_seed_email)
        existing = self.find_user_by_email(email)
        if existing:
            if "admin" not in existing["roles"]:
                existing["roles"].append("admin")
                existing["updatedAt"] = now_iso()
                if mongo.configured:
                    self.mongo_collection("users").update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"roles": existing["roles"], "updatedAt": existing["updatedAt"]}},
                    )
            return
        user = {
            "_id": new_id(),
            "email": email,
            "emailVerified": True,
            "phoneNumber": None,
            "phoneVerified": False,
            "name": "Demo Admin",
            "image": None,
            "passwordHash": hash_password(self.config.admin_seed_password),
            "roles": ["admin", "customer"],
            "preferences": {},
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "lastLoginAt": None,
        }
        if mongo.configured:
            self.mongo_collection("users").insert_one(clone(user))
            return
        self.state["users"].append(user)

    def seed_products(self, limit: int | None) -> None:
        output_dir = self.config.ingestion_output_dir
        report = run_ingestion(
            dataset_path=self.config.dataset_path,
            output_dir=output_dir,
            public_base_url=self.config.product_image_public_base_url,
            currency=self.config.demo_currency,
            limit=limit,
        )
        products_path = Path(report.outputProductsPath)
        products: list[Json] = []
        with products_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    products.append(json.loads(line))
        self.state["products"] = products
        ingestion_status = report.model_dump(mode="json")
        self.state["ingestionStatus"] = ingestion_status

        if mongo.configured:
            # Upsert all seeded products into Atlas
            from pymongo import ReplaceOne
            if products:
                ops = [
                    ReplaceOne(
                        {"source": p["source"], "sourceProductId": p["sourceProductId"]},
                        p,
                        upsert=True,
                    )
                    for p in products
                ]
                self.mongo_collection("products").bulk_write(ops, ordered=False)
            self.mongo_collection("serviceMetadata").replace_one(
                {"_id": "ingestionStatus"}, {"_id": "ingestionStatus", "data": ingestion_status}, upsert=True
            )

    def seed_support_audit_log(self) -> None:
        if mongo.configured:
            if self.mongo_collection("agentToolAuditLogs").count_documents({}) > 0:
                return
            user_doc = self.mongo_collection("users").find_one({})
            if not user_doc:
                return
            user_id = str(user_doc["_id"])
        else:
            if self.state["agentToolAuditLogs"]:
                return
            if not self.state["users"]:
                return
            user_id = self.state["users"][0]["_id"]

        log = {
            "_id": new_id(),
            "sessionId": new_id(),
            "userId": user_id,
            "agentType": "returns_support",
            "toolName": "seedAuditLog",
            "input": {},
            "output": {"seeded": True},
            "status": "success",
            "requiresUserConfirmation": False,
            "confirmedAt": None,
            "createdAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("agentToolAuditLogs").insert_one(clone(log))
        else:
            self.state["agentToolAuditLogs"].append(log)

    # ── Identity ─────────────────────────────────────────────────────────────

    def public_user(self, user: Json) -> Json:
        public = clone(user)
        public.pop("passwordHash", None)
        return public

    def find_user_by_email(self, email: str) -> Json | None:
        normalized = normalize_email(email)
        if mongo.configured:
            return self.normalize_mongo_record(self.mongo_collection("users").find_one({"email": normalized}))
        return next((u for u in self.state["users"] if u["email"] == normalized), None)

    def find_user_by_id(self, user_id: str) -> Json | None:
        if mongo.configured:
            return self.normalize_mongo_record(self.mongo_collection("users").find_one({"_id": user_id}))
        return next((u for u in self.state["users"] if u["_id"] == user_id), None)

    def find_verified_user_by_phone(self, phone_number: str) -> Json | None:
        """Return the unique verified user matched by a caller ANI."""

        normalized = normalize_phone_number(phone_number)
        if mongo.configured:
            return self.normalize_mongo_record(
                self.mongo_collection("users").find_one({"phoneNumber": normalized, "phoneVerified": True})
            )
        return next(
            (
                user
                for user in self.state["users"]
                if user.get("phoneNumber") == normalized and user.get("phoneVerified") is True
            ),
            None,
        )

    def set_development_verified_phone(self, user_id: str, phone_number: str) -> Json:
        """Set a verified phone number in development only.

        This endpoint intentionally exists only until a real SMS verification
        provider is selected. Production callers must not self-verify a number.
        """

        if self.config.app_env != "development":
            raise ValueError("PHONE_VERIFICATION_NOT_AVAILABLE")
        user = self.find_user_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        normalized = normalize_phone_number(phone_number)
        existing = self.find_verified_user_by_phone(normalized)
        if existing and existing["_id"] != user_id:
            raise ValueError("PHONE_NUMBER_ALREADY_EXISTS")
        user["phoneNumber"] = normalized
        user["phoneVerified"] = True
        user["updatedAt"] = now_iso()
        if mongo.configured:
            try:
                self.mongo_collection("users").update_one(
                    {"_id": user_id},
                    {"$set": {"phoneNumber": normalized, "phoneVerified": True, "updatedAt": user["updatedAt"]}},
                )
            except Exception as exc:
                if "duplicate" in str(exc).lower():
                    raise ValueError("PHONE_NUMBER_ALREADY_EXISTS") from exc
                raise StoreError(f"Unable to save user phone number: {exc}") from exc
        else:
            self.save()
        return self.public_user(user)

    def verify_caller_by_order(self, order_number: str, last_name: str | None, postal_code: str | None) -> str | None:
        """Return an owning user ID only when one supplied proof matches."""

        if mongo.configured:
            order = self.normalize_mongo_record(self.mongo_collection("orders").find_one({"orderNumber": order_number}))
        else:
            order = next((item for item in self.state["orders"] if item.get("orderNumber") == order_number), None)
        if not order:
            return None
        address = order.get("shippingAddress") or {}
        name = str(address.get("name") or "").strip().lower().split()
        name_matches = bool(last_name and name and name[-1] == last_name.strip().lower())
        postal_matches = bool(postal_code and str(address.get("postalCode") or "").strip() == postal_code.strip())
        return str(order["userId"]) if name_matches or postal_matches else None

    def register_user(self, email: str, password: str, name: str) -> Json:
        normalized = normalize_email(email)
        if self.find_user_by_email(normalized):
            raise ValueError("EMAIL_ALREADY_EXISTS")
        user = {
            "_id": new_id(),
            "email": normalized,
            "emailVerified": False,
            "phoneNumber": None,
            "phoneVerified": False,
            "name": name,
            "image": None,
            "passwordHash": hash_password(password),
            "roles": ["customer"],
            "preferences": {},
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "lastLoginAt": None,
        }
        if mongo.configured:
            try:
                self.mongo_collection("users").insert_one(clone(user))
            except Exception as exc:
                if "duplicate" in str(exc).lower():
                    raise ValueError("EMAIL_ALREADY_EXISTS") from exc
                raise StoreError(f"Unable to register MongoDB user: {exc}") from exc
            return self.public_user(user)
        self.state["users"].append(user)
        self.save()
        return self.public_user(user)

    def login_user(self, email: str, password: str) -> tuple[Json, str]:
        user = self.find_user_by_email(email)
        if not user or not verify_password(password, user["passwordHash"]):
            raise ValueError("INVALID_CREDENTIALS")
        token = self.create_session_for_user(user)
        return self.public_user(user), token

    def create_session_for_user(self, user: Json) -> str:
        token = secrets.token_urlsafe(32)
        user["lastLoginAt"] = now_iso()
        session = {
            "_id": new_id(),
            "userId": user["_id"],
            "sessionTokenHash": hash_token(token),
            "expiresAt": (datetime.now(UTC) + timedelta(seconds=self.config.session_cookie_max_age_seconds)).isoformat().replace("+00:00", "Z"),
            "createdAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("sessions").insert_one(clone(session))
            self.mongo_collection("users").update_one({"_id": user["_id"]}, {"$set": {"lastLoginAt": user["lastLoginAt"]}})
            return token
        self.state["sessions"].append(session)
        self.save()
        return token

    def upsert_google_user(self, email: str, name: str, image: str | None) -> Json:
        normalized = normalize_email(email)
        user = self.find_user_by_email(normalized)
        if user:
            user["name"] = name or user["name"]
            user["image"] = image or user.get("image")
            user["emailVerified"] = True
            providers = user.setdefault("identityProviders", [])
            if "google" not in providers:
                providers.append("google")
            user["updatedAt"] = now_iso()
            if mongo.configured:
                self.mongo_collection("users").update_one(
                    {"_id": user["_id"]},
                    {"$set": {"name": user["name"], "image": user["image"], "emailVerified": True, "identityProviders": providers, "updatedAt": user["updatedAt"]}},
                )
                return self.public_user(user)
            self.save()
            return self.public_user(user)
        user = {
            "_id": new_id(),
            "email": normalized,
            "emailVerified": True,
            "phoneNumber": None,
            "phoneVerified": False,
            "name": name,
            "image": image,
            "passwordHash": "",
            "identityProviders": ["google"],
            "roles": ["customer"],
            "preferences": {},
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "lastLoginAt": None,
        }
        if mongo.configured:
            self.mongo_collection("users").insert_one(clone(user))
            return self.public_user(user)
        self.state["users"].append(user)
        self.save()
        return self.public_user(user)

    def user_for_session_token(self, token: str | None) -> Json | None:
        if not token:
            return None
        token_hash = hash_token(token)
        if mongo.configured:
            session = self.normalize_mongo_record(self.mongo_collection("sessions").find_one({"sessionTokenHash": token_hash}))
            if not session:
                return None
            expires_at = datetime.fromisoformat(str(session["expiresAt"]).replace("Z", "+00:00"))
            if expires_at < datetime.now(UTC):
                self.mongo_collection("sessions").delete_one({"_id": session["_id"]})
                return None
            return self.find_user_by_id(session["userId"])
        session = next((s for s in self.state["sessions"] if s["sessionTokenHash"] == token_hash), None)
        if not session:
            return None
        return self.find_user_by_id(session["userId"])

    def logout(self, token: str | None) -> None:
        if not token:
            return
        token_hash = hash_token(token)
        if mongo.configured:
            self.mongo_collection("sessions").delete_many({"sessionTokenHash": token_hash})
            return
        self.state["sessions"] = [s for s in self.state["sessions"] if s["sessionTokenHash"] != token_hash]
        self.save()

    def update_user_preference(self, user_id: str, key: str, value: Any) -> Json:
        user = self.find_user_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        preferences = user.setdefault("preferences", {})
        preferences[key] = clone(value)
        user["updatedAt"] = now_iso()
        if mongo.configured:
            self.mongo_collection("users").update_one(
                {"_id": user_id},
                {"$set": {f"preferences.{key}": clone(value), "updatedAt": user["updatedAt"]}},
            )
            return self.public_user(user)
        self.save()
        return self.public_user(user)

    def create_password_reset_token(self, email: str) -> str | None:
        user = self.find_user_by_email(email)
        if not user:
            return None
        token = secrets.token_urlsafe(32)
        record = {
            "_id": new_id(),
            "userId": user["_id"],
            "tokenHash": hash_token(token),
            "expiresAt": (datetime.now(UTC) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "consumedAt": None,
            "createdAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("passwordResetTokens").insert_one(clone(record))
            return token
        self.state.setdefault("passwordResetTokens", []).append(record)
        self.save()
        return token

    def reset_password(self, token: str, password: str) -> Json:
        token_hash = hash_token(token)
        if mongo.configured:
            record = self.normalize_mongo_record(
                self.mongo_collection("passwordResetTokens").find_one({"tokenHash": token_hash, "consumedAt": None})
            )
            if not record:
                raise ValueError("INVALID_RESET_TOKEN")
            expires_at = datetime.fromisoformat(str(record["expiresAt"]).replace("Z", "+00:00"))
            if expires_at < datetime.now(UTC):
                raise ValueError("INVALID_RESET_TOKEN")
            user = self.find_user_by_id(record["userId"])
            if not user:
                raise ValueError("INVALID_RESET_TOKEN")
            password_hash = hash_password(password)
            updated_at = now_iso()
            consumed_at = now_iso()
            self.mongo_collection("users").update_one({"_id": user["_id"]}, {"$set": {"passwordHash": password_hash, "updatedAt": updated_at}})
            self.mongo_collection("passwordResetTokens").update_one({"_id": record["_id"]}, {"$set": {"consumedAt": consumed_at}})
            user["passwordHash"] = password_hash
            user["updatedAt"] = updated_at
            return self.public_user(user)
        reset_tokens = self.state.setdefault("passwordResetTokens", [])
        record = next((r for r in reset_tokens if r["tokenHash"] == token_hash and not r.get("consumedAt")), None)
        if not record:
            raise ValueError("INVALID_RESET_TOKEN")
        expires_at = datetime.fromisoformat(str(record["expiresAt"]).replace("Z", "+00:00"))
        if expires_at < datetime.now(UTC):
            raise ValueError("INVALID_RESET_TOKEN")
        user = self.find_user_by_id(record["userId"])
        if not user:
            raise ValueError("INVALID_RESET_TOKEN")
        user["passwordHash"] = hash_password(password)
        user["updatedAt"] = now_iso()
        record["consumedAt"] = now_iso()
        self.save()
        return self.public_user(user)

    # ── Products ─────────────────────────────────────────────────────────────

    def list_products(self, limit: int, page: int, query: str | None = None) -> Json:
        if mongo.configured:
            match: Json = {"isActive": {"$ne": False}}
            if query:
                match["$or"] = [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"tags": {"$regex": query, "$options": "i"}},
                ]
            total = self.mongo_collection("products").count_documents(match)
            skip = max(page - 1, 0) * limit
            items = self._docs(self.mongo_collection("products").find(match).skip(skip).limit(limit))
            return {"items": items, "total": total, "page": page, "limit": limit}
        products = [p for p in self.state["products"] if p.get("isActive", True)]
        if query:
            lowered = query.lower()
            products = [
                p for p in products
                if lowered in json.dumps({"title": p.get("title"), "description": p.get("description"), "tags": p.get("tags"), "baseColour": p.get("baseColour")}).lower()
            ]
        start = max(page - 1, 0) * limit
        return {"items": clone(products[start : start + limit]), "total": len(products), "page": page, "limit": limit}

    def product_facets(self) -> Json:
        if mongo.configured:
            products = self._docs(self.mongo_collection("products").find({"isActive": {"$ne": False}}))
        else:
            products = [p for p in self.state["products"] if p.get("isActive", True)]
        facet_names = ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]
        facets: Json = {}
        for name in facet_names:
            values = sorted({str(p.get(name)) for p in products if p.get(name)})
            facets[name] = [{"value": v, "count": sum(1 for p in products if str(p.get(name)) == v)} for v in values]
        prices = [float(p["price"]["amount"]) for p in products if p.get("price")]
        facets["price"] = {"min": min(prices) if prices else 0, "max": max(prices) if prices else 0, "currency": self.config.demo_currency}
        return facets

    def find_product(self, product_id: str) -> Json | None:
        local = next(
            (p for p in self.state["products"] if p.get("_id") == product_id or p.get("sourceProductId") == product_id or p.get("slug") == product_id),
            None,
        )
        if local:
            return local
        return self.find_atlas_product(product_id)

    def find_atlas_product(self, product_id: str) -> Json | None:
        if not mongo.configured:
            return None
        object_id: Any | None = None
        try:
            from bson import ObjectId
            if ObjectId.is_valid(product_id):
                object_id = ObjectId(product_id)
        except ImportError:
            object_id = None
        candidates: list[Json] = [{"_id": product_id}, {"sourceProductId": product_id}, {"slug": product_id}]
        if object_id is not None:
            candidates.insert(0, {"_id": object_id})
        try:
            product = self.mongo_collection("products").find_one({"isActive": {"$ne": False}, "$or": candidates})
        except Exception:
            return None
        if not isinstance(product, dict):
            return None
        return clone(product)

    # ── Sequential counters ───────────────────────────────────────────────────

    def next_number(self, counter_name: str, prefix: str) -> str:
        if mongo.configured:
            result = self.mongo_collection("counters").find_one_and_update(
                {"_id": counter_name},
                {"$inc": {"value": 1}},
                upsert=True,
                return_document=True,
            )
            count = int(result["value"])
        else:
            self.state["counters"][counter_name] = int(self.state["counters"].get(counter_name, 0)) + 1
            count = self.state["counters"][counter_name]
        today = datetime.now(UTC).strftime("%Y%m%d")
        return f"{prefix}-{today}-{count:06d}"

    # ── Carts ─────────────────────────────────────────────────────────────────

    def identity_key(self, user: Json | None, anonymous_id: str) -> tuple[str | None, str | None]:
        return (user["_id"], None) if user else (None, anonymous_id)

    def get_or_create_cart(self, user: Json | None, anonymous_id: str) -> Json:
        user_id, anon_id = self.identity_key(user, anonymous_id)
        if mongo.configured:
            query: Json = {"status": "active"}
            if user_id:
                query["userId"] = user_id
            else:
                query["anonymousId"] = anon_id
            doc = self.normalize_mongo_record(self.mongo_collection("carts").find_one(query))
            if doc:
                return doc
            cart = {
                "_id": new_id(),
                "userId": user_id,
                "anonymousId": anon_id,
                "status": "active",
                "items": [],
                "totals": self.calculate_totals([]),
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
            }
            self.mongo_collection("carts").insert_one(clone(cart))
            return cart
        for cart in self.state["carts"]:
            if cart["status"] == "active" and cart.get("userId") == user_id and cart.get("anonymousId") == anon_id:
                return cart
        cart = {
            "_id": new_id(),
            "userId": user_id,
            "anonymousId": anon_id,
            "status": "active",
            "items": [],
            "totals": self.calculate_totals([]),
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        self.state["carts"].append(cart)
        return cart

    def calculate_totals(self, items: list[Json]) -> Json:
        subtotal = round(sum(float(item["priceSnapshot"]["amount"]) * int(item["quantity"]) for item in items), 2)
        tax = round(subtotal * (self.config.demo_tax_percent / 100), 2)
        shipping = 0.0 if subtotal >= self.config.demo_free_shipping_threshold or subtotal == 0 else self.config.demo_shipping_fee
        return {"subtotal": subtotal, "tax": tax, "shipping": shipping, "discount": 0.0, "grandTotal": round(subtotal + tax + shipping, 2), "currency": self.config.demo_currency}

    def _save_cart(self, cart: Json) -> None:
        """Persist a cart document."""
        if mongo.configured:
            self.mongo_collection("carts").replace_one({"_id": cart["_id"]}, clone(cart), upsert=True)
        else:
            self.save()

    def touch_cart(self, cart: Json) -> Json:
        cart["totals"] = self.calculate_totals(cart["items"])
        cart["updatedAt"] = now_iso()
        self._save_cart(cart)
        return clone(cart)

    def add_cart_item(self, user: Json | None, anonymous_id: str, product_id: str, quantity: int, size: str | None) -> Json:
        product = self.find_product(product_id)
        if not product:
            raise ValueError("PRODUCT_NOT_FOUND")
        cart = self.get_or_create_cart(user, anonymous_id)
        item = {
            "cartItemId": str(uuid.uuid4()),
            "productId": product["_id"],
            "sourceProductId": product["sourceProductId"],
            "titleSnapshot": product["title"],
            "priceSnapshot": clone(product["price"]),
            "imageUrlSnapshot": (product.get("images") or [{}])[0].get("url"),
            "size": size,
            "quantity": quantity,
            "addedAt": now_iso(),
            "updatedAt": now_iso(),
        }
        cart["items"].append(item)
        self.touch_cart(cart)
        self.add_activity("cart_item_added", {"cartId": cart["_id"], "productId": product["_id"]}, user, anonymous_id)
        return clone(item)

    def update_cart_item(self, user: Json | None, anonymous_id: str, cart_item_id: str, quantity: int) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        item = next((e for e in cart["items"] if e["cartItemId"] == cart_item_id), None)
        if not item:
            raise ValueError("CART_ITEM_NOT_FOUND")
        if quantity == 0:
            cart["items"] = [e for e in cart["items"] if e["cartItemId"] != cart_item_id]
            self.touch_cart(cart)
            return clone(item)
        item["quantity"] = quantity
        item["updatedAt"] = now_iso()
        self.touch_cart(cart)
        self.add_activity("cart_item_updated", {"cartId": cart["_id"], "cartItemId": cart_item_id}, user, anonymous_id)
        return clone(item)

    def remove_cart_item(self, user: Json | None, anonymous_id: str, cart_item_id: str) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        item = next((e for e in cart["items"] if e["cartItemId"] == cart_item_id), None)
        if not item:
            raise ValueError("CART_ITEM_NOT_FOUND")
        cart["items"] = [e for e in cart["items"] if e["cartItemId"] != cart_item_id]
        self.touch_cart(cart)
        self.add_activity("cart_item_removed", {"cartId": cart["_id"], "cartItemId": cart_item_id}, user, anonymous_id)
        return clone(item)

    def clear_cart(self, user: Json | None, anonymous_id: str) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        cart["items"] = []
        return self.touch_cart(cart)

    def cart_snapshot(self, user: Json | None, anonymous_id: str) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        return self.touch_cart(cart)

    def merge_cart(self, user: Json, anonymous_id: str) -> Json:
        anon_cart = self.get_or_create_cart(None, anonymous_id)
        user_cart = self.get_or_create_cart(user, anonymous_id)
        if anon_cart["_id"] != user_cart["_id"]:
            user_cart["items"].extend(clone(anon_cart["items"]))
            anon_cart["status"] = "merged"
            if mongo.configured:
                self.mongo_collection("carts").update_one({"_id": anon_cart["_id"]}, {"$set": {"status": "merged", "updatedAt": now_iso()}})
        return self.touch_cart(user_cart)

    # ── Orders ────────────────────────────────────────────────────────────────

    def place_order(self, user: Json, anonymous_id: str, shipping_address: Json, payment_method: str) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        if not cart["items"]:
            raise ValueError("CART_EMPTY")
        totals = self.calculate_totals(cart["items"])
        order_number = self.next_number("order", "ORD")
        order = {
            "_id": new_id(),
            "orderNumber": order_number,
            "userId": user["_id"],
            "status": "confirmed",
            "items": [
                {
                    "orderItemId": str(uuid.uuid4()),
                    "productId": item["productId"],
                    "sourceProductId": item["sourceProductId"],
                    "titleSnapshot": item["titleSnapshot"],
                    "imageUrlSnapshot": ((self.find_product(item["productId"]) or {}).get("images") or [{"url": ""}])[0].get("url", ""),
                    "size": item.get("size"),
                    "quantity": item["quantity"],
                    "unitPrice": item["priceSnapshot"],
                    "returnStatus": "eligible",
                }
                for item in cart["items"]
            ],
            "shippingAddress": shipping_address,
            "totals": totals,
            "payment": {"provider": payment_method, "status": "paid", "transactionId": f"demo_txn_{new_id()}"},
            "shipment": self.shipment_for_order_number(order_number),
            "placedAt": now_iso(),
            "estimatedDeliveryAt": (datetime.now(UTC) + timedelta(days=5)).isoformat().replace("+00:00", "Z"),
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("orders").insert_one(clone(order))
        else:
            self.state["orders"].append(order)
        cart["items"] = []
        self.touch_cart(cart)
        self.add_activity("order_placed", {"orderId": order["_id"], "orderNumber": order["orderNumber"]}, user, anonymous_id)
        if not mongo.configured:
            self.save()
        return clone(order)

    def shipment_for_order_number(self, order_number: str, order_status: str = "confirmed") -> Json:
        """Create deterministic synthetic shipment facts from an order number."""

        digest = hashlib.sha256(order_number.encode("utf-8")).hexdigest()
        carrier = ("BlueDart", "Delhivery", "DTDC", "FedEx")[int(digest[:2], 16) % 4]
        status = "delivered" if order_status == "delivered" else "pending"
        timestamp = now_iso()
        tracking_number = f"{carrier[:3].upper()}-{digest[:12].upper()}"
        return {
            "carrier": carrier,
            "trackingNumber": tracking_number,
            "trackingUrl": f"https://tracking.example.test/{tracking_number}",
            "status": status,
            "shippedAt": None,
            "estimatedDeliveryAt": (datetime.now(UTC) + timedelta(days=5)).isoformat().replace("+00:00", "Z"),
            "deliveredAt": timestamp if status == "delivered" else None,
        }

    def _ensure_shipment(self, order: Json) -> Json:
        if order.get("shipment"):
            return order
        order["shipment"] = self.shipment_for_order_number(str(order["orderNumber"]), str(order.get("status") or "confirmed"))
        order["updatedAt"] = now_iso()
        if mongo.configured:
            self.mongo_collection("orders").update_one({"_id": order["_id"]}, {"$set": {"shipment": order["shipment"], "updatedAt": order["updatedAt"]}})
        else:
            self.save()
        return order

    def user_orders(self, user: Json) -> list[Json]:
        if mongo.configured:
            return [clone(self._ensure_shipment(order)) for order in self._docs(self.mongo_collection("orders").find({"userId": user["_id"]}).sort("createdAt", -1))]
        return [clone(self._ensure_shipment(order)) for order in self.state["orders"] if order["userId"] == user["_id"]]

    def find_order_for_user(self, user: Json, order_id_or_number: str) -> Json | None:
        if mongo.configured:
            doc = self.mongo_collection("orders").find_one({
                "userId": user["_id"],
                "$or": [{"_id": order_id_or_number}, {"orderNumber": order_id_or_number}],
            })
            return self._ensure_shipment(self.normalize_mongo_record(doc)) if doc else None
        order = next(
            (o for o in self.state["orders"] if o["userId"] == user["_id"] and (o["_id"] == order_id_or_number or o["orderNumber"] == order_id_or_number)),
            None,
        )
        return self._ensure_shipment(order) if order else None

    def payment_details(self, user: Json, order_id_or_number: str) -> Json:
        order = self.find_order_for_user(user, order_id_or_number)
        if not order:
            raise ValueError("ORDER_NOT_FOUND")
        payment = order.get("payment") or {}
        return {
            "orderNumber": order["orderNumber"],
            "status": payment.get("status"),
            "method": payment.get("provider"),
            "amount": (order.get("totals") or {}).get("grandTotal"),
            "currency": (order.get("totals") or {}).get("currency"),
        }

    def update_order(self, user: Json, order_id_or_number: str, action: str, shipping_address: Json | None) -> Json:
        order = self.find_order_for_user(user, order_id_or_number)
        if not order:
            raise ValueError("ORDER_NOT_FOUND")
        shipment_status = str((order.get("shipment") or {}).get("status") or "pending")
        pre_dispatch = shipment_status in {"pending", "label_created"}
        if action == "cancel":
            if order.get("status") == "cancelled":
                return clone(order)
            if not pre_dispatch:
                raise ValueError("ORDER_UPDATE_NOT_ALLOWED")
            order["status"] = "cancelled"
            order["cancelledAt"] = now_iso()
            order["cancelledBy"] = user["_id"]
        elif action == "update_shipping_address":
            if not pre_dispatch:
                raise ValueError("ORDER_UPDATE_NOT_ALLOWED")
            if not shipping_address:
                raise ValueError("SHIPPING_ADDRESS_REQUIRED")
            order["shippingAddress"] = clone(shipping_address)
        else:
            raise ValueError("UNSUPPORTED_ORDER_UPDATE")
        order["updatedAt"] = now_iso()
        if mongo.configured:
            self.mongo_collection("orders").replace_one({"_id": order["_id"]}, clone(order), upsert=False)
        else:
            self.save()
        self.add_activity("order_updated", {"orderId": order["_id"], "action": action}, user, None)
        return clone(order)

    def checkout_quote(self, user: Json, anonymous_id: str, shipping_address: Json) -> Json:
        cart = self.get_or_create_cart(user, anonymous_id)
        totals = self.calculate_totals(cart["items"])
        self.add_activity("checkout_started", {"cartId": cart["_id"], "shippingCountry": shipping_address.get("country")}, user, anonymous_id)
        return {"cartId": cart["_id"], "items": clone(cart["items"]), "totals": totals, "shippingAddress": clone(shipping_address), "paymentProvider": "demo"}

    # ── Returns ───────────────────────────────────────────────────────────────

    def check_return_eligibility(self, user: Json, order_id: str, order_item_id: str) -> Json:
        order = self.find_order_for_user(user, order_id)
        if not order:
            raise ValueError("ORDER_NOT_FOUND")
        item = next((e for e in order["items"] if e["orderItemId"] == order_item_id), None)
        if not item:
            raise ValueError("ORDER_ITEM_NOT_FOUND")
        return {
            "eligible": item.get("returnStatus") == "eligible",
            "policyCode": "standard-30-day",
            "returnWindowEndsAt": (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
            "orderItemId": order_item_id,
        }

    def create_return(self, user: Json, anonymous_id: str, order_id: str, items: list[Json]) -> Json:
        order = self.find_order_for_user(user, order_id)
        if not order:
            raise ValueError("ORDER_NOT_FOUND")
        return_request = {
            "_id": new_id(),
            "returnNumber": self.next_number("return", "RET"),
            "userId": user["_id"],
            "orderId": order["_id"],
            "orderNumber": order["orderNumber"],
            "items": items,
            "status": "requested",
            "eligibility": {"eligible": True, "policyCode": "standard-30-day"},
            "agentSessionId": None,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("returnRequests").insert_one(clone(return_request))
        else:
            self.state["returnRequests"].append(return_request)
            self.save()
        self.add_activity("return_requested", {"orderId": order["_id"], "returnNumber": return_request["returnNumber"]}, user, anonymous_id)
        return clone(return_request)

    # ── Support tickets ───────────────────────────────────────────────────────

    def create_ticket(self, user: Json, anonymous_id: str, payload: Json) -> Json:
        if payload.get("orderId") and not self.find_order_for_user(user, payload["orderId"]):
            raise ValueError("ORDER_NOT_FOUND")
        ticket = {
            "_id": new_id(),
            "ticketNumber": self.next_number("ticket", "SUP"),
            "userId": user["_id"],
            "orderId": payload.get("orderId"),
            "category": payload["category"],
            "priority": payload["priority"],
            "subject": payload["subject"],
            "status": "open",
            "messages": [{"senderType": "customer", "message": payload["body"], "createdAt": now_iso()}],
            "agentSessionId": None,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("supportTickets").insert_one(clone(ticket))
        else:
            self.state["supportTickets"].append(ticket)
            self.save()
        self.add_activity("support_ticket_created", {"ticketNumber": ticket["ticketNumber"], "orderId": ticket["orderId"]}, user, anonymous_id)
        return clone(ticket)

    def add_ticket_message(self, user: Json, ticket_number: str, message: str) -> Json:
        if mongo.configured:
            ticket = self.normalize_mongo_record(
                self.mongo_collection("supportTickets").find_one({"ticketNumber": ticket_number, "userId": user["_id"]})
            )
            if not ticket:
                raise ValueError("TICKET_NOT_FOUND")
            item = {"senderType": "customer", "message": message, "createdAt": now_iso()}
            self.mongo_collection("supportTickets").update_one(
                {"_id": ticket["_id"]},
                {"$push": {"messages": item}, "$set": {"updatedAt": now_iso()}},
            )
            return clone(item)
        ticket = next(
            (t for t in self.state["supportTickets"] if t["ticketNumber"] == ticket_number and t["userId"] == user["_id"]),
            None,
        )
        if not ticket:
            raise ValueError("TICKET_NOT_FOUND")
        item = {"senderType": "customer", "message": message, "createdAt": now_iso()}
        ticket["messages"].append(item)
        ticket["updatedAt"] = now_iso()
        self.save()
        return clone(item)

    def user_tickets(self, user: Json) -> list[Json]:
        if mongo.configured:
            return self._docs(self.mongo_collection("supportTickets").find({"userId": user["_id"]}).sort("createdAt", -1))
        return [clone(t) for t in self.state["supportTickets"] if t["userId"] == user["_id"]]

    def find_ticket_for_user(self, user: Json, ticket_number: str) -> Json | None:
        if mongo.configured:
            return self.normalize_mongo_record(
                self.mongo_collection("supportTickets").find_one({"ticketNumber": ticket_number, "userId": user["_id"]})
            )
        return next(
            (clone(t) for t in self.state["supportTickets"] if t["ticketNumber"] == ticket_number and t["userId"] == user["_id"]),
            None,
        )

    # ── Activity and audit ────────────────────────────────────────────────────

    def add_activity(self, event_type: str, metadata: Json, user: Json | None, anonymous_id: str | None) -> Json:
        event = {
            "_id": new_id(),
            "userId": user["_id"] if user else None,
            "anonymousId": anonymous_id,
            "sessionId": anonymous_id,
            "eventType": event_type,
            "eventSource": "web",
            "occurredAt": now_iso(),
            "metadata": clone(metadata),
            "requestId": new_id(),
            "createdAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("userActivityEvents").insert_one(clone(event))
        else:
            self.state["userActivityEvents"].append(event)
            self.save()
        return event

    def list_activity_events(self, event_type: str | None, limit: int) -> list[Json]:
        if mongo.configured:
            query: Json = {}
            if event_type:
                query["eventType"] = event_type
            return self._docs(self.mongo_collection("userActivityEvents").find(query).sort("occurredAt", -1).limit(limit))
        events = self.state["userActivityEvents"]
        if event_type:
            events = [e for e in events if e.get("eventType") == event_type]
        return [clone(e) for e in reversed(events[-limit:])]

    def add_audit_log(self, payload: Json) -> Json:
        log = {
            "_id": new_id(),
            "sessionId": payload["sessionId"],
            "userId": payload.get("userId"),
            "agentType": payload["agentType"],
            "toolName": payload["toolName"],
            "input": clone(payload.get("input") or {}),
            "output": clone(payload.get("output") or {}),
            "status": payload["status"],
            "requiresUserConfirmation": bool(payload.get("requiresUserConfirmation", False)),
            "confirmedAt": payload.get("confirmedAt"),
            "createdAt": now_iso(),
        }
        if mongo.configured:
            self.mongo_collection("agentToolAuditLogs").insert_one(clone(log))
        else:
            self.state["agentToolAuditLogs"].append(log)
            self.save()
        return clone(log)

    def list_audit_logs(self, agent_type: str | None, limit: int) -> list[Json]:
        if mongo.configured:
            query: Json = {}
            if agent_type:
                query["agentType"] = agent_type
            return self._docs(self.mongo_collection("agentToolAuditLogs").find(query).sort("createdAt", -1).limit(limit))
        logs = self.state["agentToolAuditLogs"]
        if agent_type:
            logs = [log for log in logs if log.get("agentType") == agent_type]
        return [clone(log) for log in reversed(logs[-limit:])]

    # ── Ingestion status ──────────────────────────────────────────────────────

    def ingestion_status(self) -> Json:
        if mongo.configured:
            ingestion_meta = self.mongo_collection("serviceMetadata").find_one({"_id": "ingestionStatus"})
            embedding_meta = self.mongo_collection("serviceMetadata").find_one({"_id": "embeddingStatus"})
            report = (ingestion_meta or {}).get("data") or self.state.get("ingestionStatus") or {}
            embedding = (embedding_meta or {}).get("data") or self.state.get("embeddingStatus") or {}
            products_imported = int(
                report.get("productsInserted") or report.get("productsProcessed")
                or self.mongo_collection("products").count_documents({"isActive": {"$ne": False}})
            )
        else:
            report = self.state.get("ingestionStatus") or {}
            embedding = self.state.get("embeddingStatus") or {}
            products_imported = int(report.get("productsInserted") or report.get("productsProcessed") or len(self.state["products"]))

        embeddings_generated = int(embedding.get("count") or 0)
        return {
            "datasetName": self.config.dataset_name,
            "productsImported": products_imported,
            "embeddingsGenerated": embeddings_generated,
            "imageStorage": "local_filesystem",
            "datasetPath": str(self.config.dataset_path),
            "stylesCsvRows": int(report.get("stylesCsvRows") or 0),
            "imagesCsvRows": int(report.get("imagesCsvRows") or 0),
            "jsonMetadataFiles": int(report.get("jsonMetadataFiles") or 0),
            "localImageFiles": int(report.get("localImageFiles") or 0),
            "missingLocalImageIds": list(report.get("knownMissingLocalImageIds") or []),
            "imageLocalRoot": str(self.config.product_image_local_root),
            "s3Enabled": False,
            "embedding": {
                "provider": embedding.get("provider") or self.config.embedding_provider,
                "model": embedding.get("model") or self.config.embedding_model,
                "dimensions": int(embedding.get("dimensions") or self.config.embedding_dimensions),
                "textTemplateVersion": embedding.get("textTemplateVersion") or self.config.embedding_text_template_version,
                "vectorIndexName": embedding.get("vectorIndexName") or self.config.mongodb_vector_index_name,
            },
        }


store = CoreStore(settings)
