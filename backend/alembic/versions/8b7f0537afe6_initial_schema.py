"""initial schema

Revision ID: 8b7f0537afe6
Revises:
Create Date: 2026-02-22 14:57:40.278248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8b7f0537afe6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scan_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('imported_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('report_date', sa.DateTime(), nullable=True),
        sa.Column('asset_group', sa.String(255), nullable=True),
        sa.Column('total_vulns_declared', sa.Integer(), nullable=True),
        sa.Column('avg_risk_declared', sa.Float(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
    )

    op.create_table(
        'hosts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ip', sa.String(45), nullable=False, unique=True),
        sa.Column('dns', sa.String(255), nullable=True),
        sa.Column('netbios', sa.String(255), nullable=True),
        sa.Column('os', sa.String(500), nullable=True),
        sa.Column('os_cpe', sa.String(500), nullable=True),
        sa.Column('first_seen', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_seen', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_hosts_ip', 'hosts', ['ip'])

    op.create_table(
        'vulnerabilities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scan_report_id', sa.Integer(), sa.ForeignKey('scan_reports.id'), nullable=False),
        sa.Column('host_id', sa.Integer(), sa.ForeignKey('hosts.id'), nullable=False),
        sa.Column('qid', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(1000), nullable=False),
        sa.Column('vuln_status', sa.String(50), nullable=True),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('protocol', sa.String(20), nullable=True),
        sa.Column('fqdn', sa.String(500), nullable=True),
        sa.Column('ssl', sa.Boolean(), nullable=True),
        sa.Column('first_detected', sa.DateTime(), nullable=True),
        sa.Column('last_detected', sa.DateTime(), nullable=True),
        sa.Column('times_detected', sa.Integer(), nullable=True),
        sa.Column('date_last_fixed', sa.DateTime(), nullable=True),
        sa.Column('cve_ids', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('vendor_reference', sa.String(500), nullable=True),
        sa.Column('bugtraq_id', sa.String(255), nullable=True),
        sa.Column('cvss_base', sa.String(100), nullable=True),
        sa.Column('cvss_temporal', sa.String(100), nullable=True),
        sa.Column('cvss3_base', sa.String(100), nullable=True),
        sa.Column('cvss3_temporal', sa.String(100), nullable=True),
        sa.Column('threat', sa.Text(), nullable=True),
        sa.Column('impact', sa.Text(), nullable=True),
        sa.Column('solution', sa.Text(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('pci_vuln', sa.Boolean(), nullable=True),
        sa.Column('ticket_state', sa.String(50), nullable=True),
        sa.Column('tracking_method', sa.String(50), nullable=True),
        sa.Column('category', sa.String(255), nullable=True),
    )
    op.create_index('ix_vulnerabilities_scan_report_id', 'vulnerabilities', ['scan_report_id'])
    op.create_index('ix_vulnerabilities_host_id', 'vulnerabilities', ['host_id'])
    op.create_index('ix_vulnerabilities_qid', 'vulnerabilities', ['qid'])
    op.create_index('ix_vulnerabilities_severity', 'vulnerabilities', ['severity'])
    op.create_index('ix_vuln_report_severity', 'vulnerabilities', ['scan_report_id', 'severity'])
    op.create_index('ix_vuln_status', 'vulnerabilities', ['vuln_status'])

    op.create_table(
        'import_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scan_report_id', sa.Integer(), sa.ForeignKey('scan_reports.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('rows_processed', sa.Integer(), default=0),
        sa.Column('rows_total', sa.Integer(), default=0),
    )

    op.create_table(
        'report_coherence_checks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scan_report_id', sa.Integer(), sa.ForeignKey('scan_reports.id'), nullable=False),
        sa.Column('check_type', sa.String(50), nullable=False),
        sa.Column('entity', sa.String(255), nullable=True),
        sa.Column('expected_value', sa.String(255), nullable=False),
        sa.Column('actual_value', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_report_coherence_checks_scan_report_id', 'report_coherence_checks', ['scan_report_id'])


def downgrade() -> None:
    op.drop_table('report_coherence_checks')
    op.drop_table('import_jobs')
    op.drop_table('vulnerabilities')
    op.drop_table('hosts')
    op.drop_table('scan_reports')
