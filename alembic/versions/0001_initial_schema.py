"""Initial schema: users and roles, templates, reports and their OCR data, audit, notifications, settings.

Revision ID: 0001
Revises: 
Create Date: 2026-10-08 15:18:21.216453
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('app_settings',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_app_settings'))
    )
    op.create_table('departments',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
    sa.UniqueConstraint('code', name=op.f('uq_departments_code'))
    )
    op.create_table('report_templates',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('quantity_field_key', sa.String(length=64), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_templates')),
    sa.UniqueConstraint('code', name=op.f('uq_report_templates_code'))
    )
    op.create_table('roles',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('code', sa.Enum('ADMIN', 'QUALITY_INSPECTOR', 'OPERATOR', 'VIEWER', name='rolecode', native_enum=False, length=32), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
    sa.UniqueConstraint('code', name=op.f('uq_roles_code'))
    )
    op.create_table('users',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('correlation_id', sa.String(length=128), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('read', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_password_reset_tokens_token_hash'))
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_refresh_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash'))
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('reports',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('template_id', sa.BigInteger(), nullable=False),
    sa.Column('department_id', sa.BigInteger(), nullable=True),
    sa.Column('uploaded_by', sa.BigInteger(), nullable=False),
    sa.Column('document_name', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('status', sa.Enum('UPLOADED', 'PROCESSING', 'OCR_COMPLETED', 'VALIDATION_REQUIRED', 'VALIDATED', 'APPROVED', 'FAILED', name='reportstatus', native_enum=False, length=32), nullable=False),
    sa.Column('report_month', sa.String(length=50), nullable=True),
    sa.Column('report_date', sa.Date(), nullable=True),
    sa.Column('average_confidence', sa.Float(), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('approved_by', sa.BigInteger(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_reports_approved_by_users')),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_reports_department_id_departments')),
    sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], name=op.f('fk_reports_template_id_report_templates')),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_reports_uploaded_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reports'))
    )
    op.create_index('ix_reports_created_at', 'reports', ['created_at'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_template_id'), 'reports', ['template_id'], unique=False)
    op.create_index(op.f('ix_reports_uploaded_by'), 'reports', ['uploaded_by'], unique=False)
    op.create_table('template_fields',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('template_id', sa.BigInteger(), nullable=False),
    sa.Column('field_key', sa.String(length=64), nullable=False),
    sa.Column('label', sa.String(length=150), nullable=False),
    sa.Column('scope', sa.Enum('HEADER', 'LINE', 'FOOTER', name='fieldscope', native_enum=False, length=32), nullable=False),
    sa.Column('data_type', sa.Enum('TEXT', 'NUMBER', 'DATE', 'MONTH', name='fielddatatype', native_enum=False, length=32), nullable=False),
    sa.Column('required', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('column_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('validation_rule', sa.String(length=32), server_default='NONE', nullable=False),
    sa.Column('region_x', sa.Float(), nullable=True),
    sa.Column('region_y', sa.Float(), nullable=True),
    sa.Column('region_width', sa.Float(), nullable=True),
    sa.Column('region_height', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], name=op.f('fk_template_fields_template_id_report_templates'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_template_fields')),
    sa.UniqueConstraint('template_id', 'field_key', name=op.f('uq_template_fields_template_id_field_key'))
    )
    op.create_index(op.f('ix_template_fields_template_id'), 'template_fields', ['template_id'], unique=False)
    op.create_table('user_roles',
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('role_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_roles'))
    )
    op.create_table('ocr_extractions',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('report_id', sa.BigInteger(), nullable=False),
    sa.Column('engine', sa.String(length=50), nullable=True),
    sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], name=op.f('fk_ocr_extractions_report_id_reports'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ocr_extractions'))
    )
    op.create_index(op.f('ix_ocr_extractions_report_id'), 'ocr_extractions', ['report_id'], unique=False)
    op.create_table('report_files',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('report_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.Enum('ORIGINAL', 'PREVIEW', name='reportfilekind', native_enum=False, length=32), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], name=op.f('fk_report_files_report_id_reports'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_files')),
    sa.UniqueConstraint('report_id', 'kind', name=op.f('uq_report_files_report_id_kind'))
    )
    op.create_table('report_lines',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('report_id', sa.BigInteger(), nullable=False),
    sa.Column('row_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], name=op.f('fk_report_lines_report_id_reports'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_lines')),
    sa.UniqueConstraint('report_id', 'row_index', name=op.f('uq_report_lines_report_id_row_index'))
    )
    op.create_table('report_field_values',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('report_id', sa.BigInteger(), nullable=False),
    sa.Column('template_field_id', sa.BigInteger(), nullable=False),
    sa.Column('line_id', sa.BigInteger(), nullable=True),
    sa.Column('raw_value', sa.Text(), nullable=True),
    sa.Column('original_value', sa.Text(), nullable=True),
    sa.Column('corrected_value', sa.Text(), nullable=True),
    sa.Column('numeric_value', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('status', sa.Enum('VERIFIED', 'NEEDS_REVIEW', 'ERROR', 'EMPTY', name='fieldvaluestatus', native_enum=False, length=32), nullable=False),
    sa.Column('bbox_x', sa.Float(), nullable=True),
    sa.Column('bbox_y', sa.Float(), nullable=True),
    sa.Column('bbox_width', sa.Float(), nullable=True),
    sa.Column('bbox_height', sa.Float(), nullable=True),
    sa.Column('page_index', sa.Integer(), server_default='0', nullable=False),
    sa.Column('corrected_by', sa.BigInteger(), nullable=True),
    sa.Column('corrected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], name=op.f('fk_report_field_values_corrected_by_users')),
    sa.ForeignKeyConstraint(['line_id'], ['report_lines.id'], name=op.f('fk_report_field_values_line_id_report_lines'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], name=op.f('fk_report_field_values_report_id_reports'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_field_id'], ['template_fields.id'], name=op.f('fk_report_field_values_template_field_id_template_fields')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_field_values'))
    )
    op.create_index(op.f('ix_report_field_values_line_id'), 'report_field_values', ['line_id'], unique=False)
    op.create_index(op.f('ix_report_field_values_report_id'), 'report_field_values', ['report_id'], unique=False)
    op.create_index(op.f('ix_report_field_values_template_field_id'), 'report_field_values', ['template_field_id'], unique=False)
    op.create_table('validation_history',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('report_id', sa.BigInteger(), nullable=False),
    sa.Column('field_value_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.Enum('CORRECTED', 'VALIDATED', 'APPROVED', name='historyaction', native_enum=False, length=32), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_validation_history_actor_id_users')),
    sa.ForeignKeyConstraint(['field_value_id'], ['report_field_values.id'], name=op.f('fk_validation_history_field_value_id_report_field_values'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], name=op.f('fk_validation_history_report_id_reports'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_validation_history'))
    )
    op.create_index(op.f('ix_validation_history_report_id'), 'validation_history', ['report_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_validation_history_report_id'), table_name='validation_history')
    op.drop_table('validation_history')
    op.drop_index(op.f('ix_report_field_values_template_field_id'), table_name='report_field_values')
    op.drop_index(op.f('ix_report_field_values_report_id'), table_name='report_field_values')
    op.drop_index(op.f('ix_report_field_values_line_id'), table_name='report_field_values')
    op.drop_table('report_field_values')
    op.drop_table('report_lines')
    op.drop_table('report_files')
    op.drop_index(op.f('ix_ocr_extractions_report_id'), table_name='ocr_extractions')
    op.drop_table('ocr_extractions')
    op.drop_table('user_roles')
    op.drop_index(op.f('ix_template_fields_template_id'), table_name='template_fields')
    op.drop_table('template_fields')
    op.drop_index(op.f('ix_reports_uploaded_by'), table_name='reports')
    op.drop_index(op.f('ix_reports_template_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index('ix_reports_created_at', table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('report_templates')
    op.drop_table('departments')
    op.drop_table('app_settings')
