from __future__ import annotations

from sqlalchemy import desc, exists

from trading_ai.stock_intelligence.models import StockScannerPublicationModel

from .models import InstitutionalOpportunityModel

CURRENT_PUBLICATION_NAME = "current_stock_intelligence"


def latest_stock_intelligence_publication(
    session,
    publication_name: str = CURRENT_PUBLICATION_NAME,
    *,
    require_materialized: bool = True,
):
    """Return the latest usable Stock Intelligence publication.

    Institutional Options uses the newest publication that has actually been
    materialized into the opportunity domain. Options-only ingestion may
    republish Stock Intelligence to refresh option/dealer lineage, but it does
    not own opportunity creation. Such a newer, unmaterialized publication must
    not hide the latest underlying-owned opportunity run from the UI or the
    downstream options workflow.
    """
    query = (
        session.query(StockScannerPublicationModel)
        .filter(StockScannerPublicationModel.publication_name == publication_name)
        .filter(StockScannerPublicationModel.status.in_(("READY", "DEGRADED")))
    )
    if require_materialized:
        query = query.filter(
            exists().where(
                InstitutionalOpportunityModel.stock_scanner_run_id
                == StockScannerPublicationModel.scanner_run_id
            )
        )
    return query.order_by(desc(StockScannerPublicationModel.snapshot_timestamp)).first()


def latest_published_stock_scanner_run_id(
    session,
    publication_name: str = CURRENT_PUBLICATION_NAME,
) -> str | None:
    """Return the newest usable publication run, materialized or not."""
    publication = latest_stock_intelligence_publication(
        session,
        publication_name,
        require_materialized=False,
    )
    return None if publication is None else str(publication.scanner_run_id)


def latest_stock_scanner_run_id(
    session,
    publication_name: str = CURRENT_PUBLICATION_NAME,
) -> str | None:
    """Return the newest usable run materialized into Institutional Options."""
    publication = latest_stock_intelligence_publication(
        session,
        publication_name,
        require_materialized=True,
    )
    return None if publication is None else str(publication.scanner_run_id)


def opportunity_ids_for_stock_run(session, stock_scanner_run_id: str) -> list[str]:
    return [
        str(value)
        for (value,) in (
            session.query(InstitutionalOpportunityModel.opportunity_id)
            .filter(InstitutionalOpportunityModel.stock_scanner_run_id == stock_scanner_run_id)
            .order_by(InstitutionalOpportunityModel.opportunity_id)
            .all()
        )
    ]


def latest_opportunity_ids(
    session,
    publication_name: str = CURRENT_PUBLICATION_NAME,
) -> tuple[str | None, list[str]]:
    run_id = latest_stock_scanner_run_id(session, publication_name)
    if run_id is None:
        return None, []
    return run_id, opportunity_ids_for_stock_run(session, run_id)
