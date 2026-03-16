"""add app_settings and latest_vulns

Revision ID: f7b4c5d63a29
Revises: e6f3a4d52b18
Create Date: 2026-02-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7b4c5d63a29'
down_revision: Union[str, None] = 'e6f3a4d52b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create app_settings table
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # 2. Seed default freshness values
    op.execute(
        "INSERT INTO app_settings (key, value) VALUES "
        "('freshness_stale_days', '7'), "
        "('freshness_hide_days', '30')"
    )

    # 3. Create materialized view latest_vulns
    op.execute("""
        CREATE MATERIALIZED VIEW latest_vulns AS
        SELECT DISTINCT ON (v.host_id, v.qid)
            v.id,
            v.scan_report_id,
            v.host_id,
            v.qid,
            v.title,
            v.vuln_status,
            v.type,
            v.severity,
            v.port,
            v.protocol,
            v.fqdn,
            v.ssl,
            v.first_detected,
            v.last_detected,
            v.times_detected,
            v.date_last_fixed,
            v.cve_ids,
            v.vendor_reference,
            v.bugtraq_id,
            v.cvss_base,
            v.cvss_temporal,
            v.cvss3_base,
            v.cvss3_temporal,
            v.threat,
            v.impact,
            v.solution,
            v.results,
            v.pci_vuln,
            v.ticket_state,
            v.tracking_method,
            v.category,
            v.layer_id
        FROM vulnerabilities v
        JOIN scan_reports sr ON sr.id = v.scan_report_id
        ORDER BY v.host_id, v.qid, sr.report_date DESC NULLS LAST, v.id DESC
    """)

    # 4. Create indexes on the materialized view
    op.execute(
        "CREATE UNIQUE INDEX ix_latest_vulns_host_qid "
        "ON latest_vulns (host_id, qid)"
    )
    op.execute(
        "CREATE INDEX ix_latest_vulns_severity "
        "ON latest_vulns (severity)"
    )
    op.execute(
        "CREATE INDEX ix_latest_vulns_qid "
        "ON latest_vulns (qid)"
    )
    op.execute(
        "CREATE INDEX ix_latest_vulns_layer_id "
        "ON latest_vulns (layer_id)"
    )
    op.execute(
        "CREATE INDEX ix_latest_vulns_last_detected "
        "ON latest_vulns (last_detected)"
    )

    # 5. Add ignore_before column to watch_paths
    op.add_column(
        'watch_paths',
        sa.Column('ignore_before', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('watch_paths', 'ignore_before')
    op.execute("DROP MATERIALIZED VIEW IF EXISTS latest_vulns")
    op.drop_table('app_settings')
