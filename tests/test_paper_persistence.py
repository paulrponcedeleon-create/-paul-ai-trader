from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.database

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.repositories.paper_trading import PaperTradingRepository


def test_paper_repository_persists_account(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'paper.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        repo = PaperTradingRepository(session)
        repo.upsert_account(account_id="acct", cash_mxn=1000, status="running")
        repo.record_snapshot("acct", {"cash_mxn": 900, "equity_mxn": 950})
        session.commit()
        assert repo.list_accounts()[0]["equity_mxn"] == 950
