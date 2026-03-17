from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class ScanReport(Base):
    __tablename__ = "scan_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    report_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    asset_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_vulns_declared: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_risk_declared: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # "auto" or "manual"

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(back_populates="scan_report")
    import_jobs: Mapped[list["ImportJob"]] = relationship(back_populates="scan_report")
    coherence_checks: Mapped[list["ReportCoherenceCheck"]] = relationship(
        back_populates="scan_report"
    )


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    dns: Mapped[str | None] = mapped_column(String(255), nullable=True)
    netbios: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os: Mapped[str | None] = mapped_column(String(500), nullable=True)
    os_cpe: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(back_populates="host")


class VulnLayer(Base):
    __tablename__ = "vuln_layers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#1677ff")
    position: Mapped[int] = mapped_column(Integer, default=0)


class VulnLayerRule(Base):
    __tablename__ = "vuln_layer_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    layer_id: Mapped[int] = mapped_column(ForeignKey("vuln_layers.id"), index=True)
    match_field: Mapped[str] = mapped_column(String(20))  # "title" | "category"
    pattern: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    layer: Mapped["VulnLayer"] = relationship()


class RuleProposal(Base):
    __tablename__ = "rule_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("vuln_layers.id", ondelete="CASCADE")
    )
    pattern: Mapped[str] = mapped_column(Text)
    match_field: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    applied_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("vuln_layer_rules.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    reviewer: Mapped["User"] = relationship(foreign_keys=[reviewed_by])
    layer: Mapped["VulnLayer"] = relationship()
    applied_rule: Mapped["VulnLayerRule"] = relationship()


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_report_id: Mapped[int] = mapped_column(ForeignKey("scan_reports.id"), index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id"), index=True)
    qid: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(Text)
    vuln_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    severity: Mapped[int] = mapped_column(Integer, index=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fqdn: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    first_detected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_detected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_detected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_last_fixed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cve_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    vendor_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    bugtraq_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    cvss_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss_temporal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss3_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss3_temporal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    threat: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[str | None] = mapped_column(Text, nullable=True)
    pci_vuln: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ticket_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    layer_id: Mapped[int | None] = mapped_column(ForeignKey("vuln_layers.id"), nullable=True, index=True)

    scan_report: Mapped["ScanReport"] = relationship(back_populates="vulnerabilities")
    host: Mapped["Host"] = relationship(back_populates="vulnerabilities")
    layer: Mapped["VulnLayer | None"] = relationship()

    __table_args__ = (
        Index("ix_vuln_report_severity", "scan_report_id", "severity"),
        Index("ix_vuln_status", "vuln_status"),
        Index("ix_vuln_trends", "scan_report_id", "severity", "host_id", "layer_id", "type"),
    )


# Read-only mapping for the latest_vulns materialized view
class LatestVuln(Base):
    __tablename__ = "latest_vulns"
    # Mirror Vulnerability columns — view has identical schema
    id: Mapped[int] = mapped_column(primary_key=True)
    scan_report_id: Mapped[int] = mapped_column(Integer)
    host_id: Mapped[int] = mapped_column(Integer, index=True)
    qid: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(Text)
    vuln_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    severity: Mapped[int] = mapped_column(Integer, index=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fqdn: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    first_detected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_detected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    times_detected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_last_fixed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cve_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    vendor_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    bugtraq_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    cvss_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss_temporal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss3_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cvss3_temporal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    threat: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[str | None] = mapped_column(Text, nullable=True)
    pci_vuln: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ticket_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    layer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    granularity: Mapped[str] = mapped_column(String(10), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    dimension_value: Mapped[str] = mapped_column(String(100), nullable=False, server_default="__all__")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_trend_snapshots_lookup", "granularity", "metric", "dimension", "period"),
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_report_id: Mapped[int] = mapped_column(ForeignKey("scan_reports.id"))
    status: Mapped[str] = mapped_column(String(20))  # pending/processing/done/error
    progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)

    scan_report: Mapped["ScanReport"] = relationship(back_populates="import_jobs")


class ReportCoherenceCheck(Base):
    __tablename__ = "report_coherence_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_report_id: Mapped[int] = mapped_column(ForeignKey("scan_reports.id"), index=True)
    check_type: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_value: Mapped[str] = mapped_column(String(255))
    actual_value: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20))  # warning/error
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scan_report: Mapped["ScanReport"] = relationship(back_populates="coherence_checks")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(20))  # builtin/custom
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)
    ad_group_dn: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="profile")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_type: Mapped[str] = mapped_column(String(20))  # local/ad
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    ad_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Login security
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_token_jti: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prev_refresh_token_jti: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prev_refresh_token_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped["Profile"] = relationship(back_populates="users")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EnterprisePreset(Base):
    __tablename__ = "enterprise_presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="default")
    severities: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    layers: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    os_classes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserPreset(Base):
    __tablename__ = "user_presets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    severities: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    layers: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    os_classes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TrendConfig(Base):
    __tablename__ = "trend_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_window_days: Mapped[int] = mapped_column(Integer, default=365)
    query_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WatchPath(Base):
    __tablename__ = "watch_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True)
    pattern: Mapped[str] = mapped_column(String(100), default="*.csv")
    recursive: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ignore_before: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TrendTemplate(Base):
    __tablename__ = "trend_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    metric: Mapped[str] = mapped_column(String(50))  # total_vulns, critical_count, host_count
    group_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # severity, category, type
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UpgradeSchedule(Base):
    __tablename__ = "upgrade_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[str] = mapped_column(String(50), nullable=False)
    target_version: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notification_thresholds: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        server_default='[{"minutes_before": 2880, "level": "info"}, {"minutes_before": 120, "level": "warning"}, {"minutes_before": 15, "level": "danger"}]',
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    scheduled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[scheduled_by])


class UpgradeHistory(Base):
    __tablename__ = "upgrade_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_version: Mapped[str] = mapped_column(String(50), nullable=False)
    target_version: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    backup_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[initiated_by])
