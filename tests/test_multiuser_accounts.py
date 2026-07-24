from datetime import datetime, timezone
from decimal import Decimal

from app.db.user_models import UserAccount
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.passwords import hash_password, verify_password


def _position(position_id: str, user_id: str, amount: str = "100.00") -> dict:
    return {
        "id": position_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "status": "open",
        "source": "manual",
        "book": "btc_mxn",
        "side": "buy",
        "amount_mxn": Decimal(amount),
        "reference_price": Decimal("1000000.00"),
        "entry_fee_rate": Decimal("0"),
        "entry_fee_mxn": Decimal("0"),
        "risk_check": "manual_test",
    }


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("family-password")
    second = hash_password("family-password")

    assert first != second
    assert verify_password("family-password", first) is True
    assert verify_password("wrong-password", first) is False
    assert "family-password" not in first


def test_family_registration_creates_independent_5000_account(client):
    response = client.post(
        "/api/register",
        json={
            "username": "papa",
            "display_name": "Papá",
            "password": "password-papa",
            "registration_code": "family-demo",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "papa"
    assert response.json()["user"]["simulated_initial_capital_mxn"] == 5000.0
    account = client.get("/api/account").json()
    assert account["simulation"]["available_cash_mxn"] == 5000.0
    assert account["simulation"]["separate_from_other_users"] is True
    assert account["bot_enabled"] is True
    assert account["ai_exploration_enabled"] is True


def test_wrong_family_code_is_rejected(client):
    response = client.post(
        "/api/register",
        json={
            "username": "hermano",
            "display_name": "Hermano",
            "password": "password-hermano",
            "registration_code": "wrong-code",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Código familiar incorrecto."


def test_user_positions_and_capital_are_isolated(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    with client.app.state.db_session_factory() as session:
        SqlSimulatedOrderRepository(session, user_id="owner").add(
            _position("owner-position", "owner", "100.00")
        )
        session.commit()

    client.post("/api/logout")
    registered = client.post(
        "/api/register",
        json={
            "username": "papa",
            "display_name": "Papá",
            "password": "password-papa",
            "registration_code": "family-demo",
        },
    )
    assert registered.status_code == 201
    papa_id = registered.json()["user"]["id"]
    with client.app.state.db_session_factory() as session:
        SqlSimulatedOrderRepository(session, user_id=papa_id).add(
            _position("papa-position", papa_id, "200.00")
        )
        session.commit()

    papa_positions = client.get("/api/positions").json()
    papa_capital = client.get("/api/capital").json()
    assert [item["id"] for item in papa_positions["items"]] == ["papa-position"]
    assert papa_capital["open_invested_mxn"] == 200.0
    assert papa_capital["available_cash_mxn"] == 4800.0

    client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"username": "paul", "password": "test-password"},
    ).status_code == 200
    owner_positions = client.get("/api/positions").json()
    owner_capital = client.get("/api/capital").json()
    assert [item["id"] for item in owner_positions["items"]] == ["owner-position"]
    assert owner_capital["open_invested_mxn"] == 100.0
    assert owner_capital["available_cash_mxn"] == 4900.0


def test_bot_ai_and_shared_learning_preferences_persist(client):
    assert client.post(
        "/api/register",
        json={
            "username": "hermano",
            "display_name": "Hermano",
            "password": "password-hermano",
            "registration_code": "family-demo",
        },
    ).status_code == 201

    response = client.patch(
        "/api/account/preferences",
        json={
            "bot_enabled": False,
            "ai_exploration_enabled": False,
            "shared_learning_enabled": False,
        },
    )

    assert response.status_code == 200
    account = response.json()
    assert account["bot_enabled"] is False
    assert account["ai_exploration_enabled"] is False
    assert account["shared_learning_enabled"] is False
    assert client.get("/runtime/status").json()["startup_state"] == "disabled_by_user"


def test_bitso_credentials_are_validated_encrypted_and_never_returned(client):
    class FakePrivateBitso:
        async def balance(self):
            return {"success": True, "payload": {"balances": []}}

    client.app.state.settings.credential_encryption_key = (
        "test-credential-encryption-key-that-is-not-stored-with-users"
    )
    client.app.state.user_bitso_factory = lambda key, secret: FakePrivateBitso()
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    response = client.post(
        "/api/account/bitso",
        json={"api_key": "visible-api-key", "api_secret": "visible-api-secret"},
    )

    assert response.status_code == 200
    serialized = str(response.json())
    assert "visible-api-key" not in serialized
    assert "visible-api-secret" not in serialized
    assert response.json()["account"]["bitso"]["connected"] is True

    with client.app.state.db_session_factory() as session:
        row = session.get(UserAccount, "owner")
        assert row.bitso_api_key_encrypted != "visible-api-key"
        assert row.bitso_api_secret_encrypted != "visible-api-secret"
        assert "visible-api-key" not in row.bitso_api_key_encrypted
        assert "visible-api-secret" not in row.bitso_api_secret_encrypted

    balance = client.get("/api/account/bitso/balance")
    assert balance.status_code == 200
    assert balance.json()["source"] == "bitso_private_read_only"


def test_community_learning_response_is_aggregated_without_identity(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    response = client.get("/api/learning/community")

    assert response.status_code == 200
    payload = response.json()
    assert payload["privacy"] == "aggregated_without_usernames_or_trade_ids"
    serialized = str(payload).lower()
    assert "paul" not in serialized
    assert "username" not in serialized


def test_only_admin_can_list_family_accounts(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    assert client.get("/api/users").status_code == 200

    client.post("/api/logout")
    assert client.post(
        "/api/register",
        json={
            "username": "papa",
            "display_name": "Papá",
            "password": "password-papa",
            "registration_code": "family-demo",
        },
    ).status_code == 201
    assert client.get("/api/users").status_code == 403


def test_account_ui_contains_user_password_bot_and_bitso_controls(client):
    page = client.get("/")
    script = client.get("/static/account-settings.js")

    assert "data-registration-enabled" in page.text
    assert "/static/account-settings.js" in page.text
    assert "Crear cuenta familiar" in script.text
    assert "Bot automático" in script.text
    assert "IA exploratoria" in script.text
    assert "API secret" in script.text
    assert "Las claves están cifradas" in script.text
