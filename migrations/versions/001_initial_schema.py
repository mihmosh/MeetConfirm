"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2025-09-30 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create events table
    op.create_table('events',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('calendar_event_id', sa.Text(), nullable=False),
    sa.Column('google_resource_id', sa.Text(), nullable=True),
    sa.Column('organizer_email', sa.Text(), nullable=False),
    sa.Column('attendee_email', sa.Text(), nullable=False),
    sa.Column('start_time_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('timezone', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('confirm_token_hash', sa.Text(), nullable=False),
    sa.Column('confirm_deadline_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'confirmed', 'cancelled', 'completed')", name='check_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('calendar_event_id')
    )
    op.create_index('ix_events_calendar_event_id', 'events', ['calendar_event_id'], unique=True)
    op.create_index('ix_events_start_time_utc', 'events', ['start_time_utc'], unique=False)
    op.create_index('ix_events_status_start_time', 'events', ['status', 'start_time_utc'], unique=False)

    # Create notifications table
    op.create_table('notifications',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('event_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('channel', sa.Text(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('meta', postgresql.JSON(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("kind IN ('confirm_request', 'cancel_notice')", name='check_kind'),
    sa.CheckConstraint("channel IN ('email')", name='check_channel'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_event_id', 'notifications', ['event_id'], unique=False)

    # Create audit_logs table
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('event_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('detail', postgresql.JSON(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    op.create_index('ix_audit_logs_event_id', 'audit_logs', ['event_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_logs_event_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index('ix_notifications_event_id', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_events_status_start_time', table_name='events')
    op.drop_index('ix_events_start_time_utc', table_name='events')
    op.drop_index('ix_events_calendar_event_id', table_name='events')
    op.drop_table('events')
