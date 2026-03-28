"""Report endpoints — generate, retry, list, detail, status."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.core.schemas import PaginatedResponse
from app.database import get_db
from app.reports.models import AnalysisReport
from app.reports.schemas import GenerateReportRequest, ReportOut, ReportStatusOut
from app.reports.service import generate_report, retry_report, VALID_REPORT_TYPES

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _report_out(report: AnalysisReport, asset_symbol: str | None = None) -> ReportOut:
    """Build ReportOut from model + joined symbol."""
    return ReportOut(
        **{c.key: getattr(report, c.key) for c in AnalysisReport.__table__.columns},
        asset_symbol=asset_symbol,
    )


async def _get_report_with_symbol(db: AsyncSession, report: AnalysisReport) -> ReportOut:
    """Resolve asset_symbol for a single report."""
    symbol = None
    if report.asset_id:
        res = await db.execute(select(Asset.symbol).where(Asset.id == report.asset_id))
        symbol = res.scalar_one_or_none()
    return _report_out(report, symbol)


@router.post("/generate", response_model=ReportOut)
async def generate(req: GenerateReportRequest, db: AsyncSession = Depends(get_db)):
    """Generate an AI report. Runs synchronously — returns completed report."""
    if req.report_type not in VALID_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid report_type. Valid: {', '.join(VALID_REPORT_TYPES)}")
    try:
        report = await generate_report(
            db=db,
            report_type=req.report_type,
            asset_id=req.asset_id,
            anomaly_event_id=req.anomaly_event_id,
            alert_event_id=req.alert_event_id,
            watchlist_id=req.watchlist_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await _get_report_with_symbol(db, report)


@router.post("/{report_id}/retry", response_model=ReportOut)
async def retry(report_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retry a failed report — creates a new report with the same parameters."""
    try:
        report = await retry_report(db=db, report_id=report_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await _get_report_with_symbol(db, report)


@router.get("", response_model=PaginatedResponse[ReportOut])
async def list_reports(
    report_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List reports, newest first."""
    conditions = []
    if report_type:
        conditions.append(AnalysisReport.report_type == report_type)
    if status:
        conditions.append(AnalysisReport.status == status)
    where = and_(*conditions) if conditions else True

    count_res = await db.execute(select(func.count(AnalysisReport.id)).where(where))
    total = count_res.scalar_one()

    result = await db.execute(
        select(AnalysisReport, Asset.symbol.label("asset_symbol"))
        .outerjoin(Asset, AnalysisReport.asset_id == Asset.id)
        .where(where)
        .order_by(AnalysisReport.created_at.desc())
        .limit(limit).offset(offset)
    )
    items = [_report_out(row.AnalysisReport, row.asset_symbol) for row in result.all()]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AnalysisReport, Asset.symbol.label("asset_symbol"))
        .outerjoin(Asset, AnalysisReport.asset_id == Asset.id)
        .where(AnalysisReport.id == report_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_out(row.AnalysisReport, row.asset_symbol)


@router.get("/{report_id}/status", response_model=ReportStatusOut)
async def report_status(report_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnalysisReport).where(AnalysisReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportStatusOut(id=report.id, status=report.status, report_type=report.report_type,
                           created_at=report.created_at, completed_at=report.completed_at)
