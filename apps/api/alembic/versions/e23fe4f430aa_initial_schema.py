"""initial schema

Revision ID: e23fe4f430aa
Revises:
Create Date: 2026-04-15 18:14:56.347765

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e23fe4f430aa'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # --- Independent tables (no FKs to other app tables) ---

    op.create_table('facilities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('provider', sa.Enum('recreation_gov', 'reserve_california', name='provider'), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('parent_name', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography'), nullable=True),
    sa.Column('state', sa.Text(), nullable=True),
    sa.Column('nearest_town', sa.Text(), nullable=True),
    sa.Column('campsite_count', sa.Integer(), nullable=True),
    sa.Column('amenities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('photo_url', sa.Text(), nullable=True),
    sa.Column('booking_url', sa.Text(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'external_id')
    )
    op.create_index('facilities_location_gix', 'facilities', ['location'], unique=False, postgresql_using='gist')
    op.create_index('facilities_name_trgm', 'facilities', ['name'], unique=False, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('facilities_state_idx', 'facilities', ['state'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('phone', sa.Text(), nullable=True),
    sa.Column('notify_email', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('notify_sms', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )

    # --- Tables with FKs to facilities ---

    op.create_table('campsites',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('facility_id', sa.BigInteger(), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('site_type', sa.Text(), nullable=True),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('facility_id', 'external_id')
    )
    op.create_index('campsites_facility_idx', 'campsites', ['facility_id'], unique=False)

    op.create_table('availability_snapshots',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('facility_id', sa.BigInteger(), nullable=False),
    sa.Column('scraped_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('grid', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('snapshots_facility_month_idx', 'availability_snapshots', ['facility_id', 'month', 'scraped_at'], unique=False, postgresql_using='btree', postgresql_ops={'scraped_at': 'DESC'})

    op.create_table('current_availability',
    sa.Column('facility_id', sa.BigInteger(), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('scraped_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('grid', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('available_dates', postgresql.ARRAY(sa.Date()), nullable=False),
    sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('facility_id', 'month')
    )
    op.create_index('current_avail_dates_gin', 'current_availability', ['available_dates'], unique=False, postgresql_using='gin')

    op.create_table('scan_jobs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('facility_id', sa.BigInteger(), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('interval_minutes', sa.Integer(), nullable=False),
    sa.Column('next_run_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_run_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('last_status', sa.Text(), nullable=True),
    sa.Column('consecutive_failures', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('facility_id', 'month')
    )
    op.create_index('scan_jobs_due_idx', 'scan_jobs', ['next_run_at'], unique=False, postgresql_where='consecutive_failures < 5')

    # --- Tables with FKs to users ---

    op.create_table('watches',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('facility_ids', postgresql.ARRAY(sa.BigInteger()), nullable=True),
    sa.Column('center', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography'), nullable=True),
    sa.Column('radius_meters', sa.Integer(), nullable=True),
    sa.Column('date_start', sa.Date(), nullable=False),
    sa.Column('date_end', sa.Date(), nullable=False),
    sa.Column('nights', sa.Integer(), server_default='1', nullable=False),
    sa.Column('flexible', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('weekdays', postgresql.ARRAY(sa.Integer()), nullable=True),
    sa.Column('site_filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('scan_interval_minutes', sa.Integer(), server_default='15', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('(facility_ids IS NOT NULL AND array_length(facility_ids, 1) > 0) OR (center IS NOT NULL AND radius_meters IS NOT NULL)', name='watches_target_check'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('watches_active_idx', 'watches', ['is_active'], unique=False, postgresql_where='is_active')
    op.create_index('watches_user_idx', 'watches', ['user_id'], unique=False)

    # --- Tables with FKs to watches ---

    op.create_table('notifications',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('watch_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('facility_id', sa.BigInteger(), nullable=False),
    sa.Column('available_dates', postgresql.ARRAY(sa.Date()), nullable=False),
    sa.Column('campsite_external_ids', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('channel', sa.Text(), nullable=False),
    sa.Column('sent_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('dedup_key', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['facility_id'], ['facilities.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['watch_id'], ['watches.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('notifications_dedup_idx', 'notifications', ['dedup_key', 'sent_at'], unique=False, postgresql_ops={'sent_at': 'DESC'})
    op.create_index('notifications_watch_idx', 'notifications', ['watch_id', 'sent_at'], unique=False, postgresql_ops={'sent_at': 'DESC'})


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('notifications_watch_idx', table_name='notifications')
    op.drop_index('notifications_dedup_idx', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('watches_user_idx', table_name='watches')
    op.drop_index('watches_active_idx', table_name='watches')
    op.drop_table('watches')
    op.drop_index('scan_jobs_due_idx', table_name='scan_jobs')
    op.drop_table('scan_jobs')
    op.drop_index('current_avail_dates_gin', table_name='current_availability')
    op.drop_table('current_availability')
    op.drop_index('snapshots_facility_month_idx', table_name='availability_snapshots')
    op.drop_table('availability_snapshots')
    op.drop_index('campsites_facility_idx', table_name='campsites')
    op.drop_table('campsites')
    op.drop_table('users')
    op.drop_index('facilities_state_idx', table_name='facilities')
    op.drop_index('facilities_name_trgm', table_name='facilities')
    op.drop_index('facilities_location_gix', table_name='facilities')
    op.drop_table('facilities')
    op.execute("DROP TYPE IF EXISTS provider")
