"""add_contest_tables

Revision ID: 4921adba9912
Revises: 3860bda0532a
Create Date: 2026-10-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4921adba9912'
down_revision: Union[str, Sequence[str], None] = '3860bda0532a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('prize_1', sa.String(length=255), nullable=False),
        sa.Column('prize_2', sa.String(length=255), nullable=False),
        sa.Column('prize_3', sa.String(length=255), nullable=False),
        sa.Column('photo_file_id', sa.String(length=255), nullable=True),
        sa.Column('channel_message_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('only_new_subscribers', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('disqualified_user_ids', sa.JSON(), nullable=False),
        sa.Column('winners_snapshot', sa.JSON(), nullable=True),
        sa.Column('total_subscribers_gained', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contests_status'), 'contests', ['status'], unique=False)
    op.create_index(op.f('ix_contests_ends_at'), 'contests', ['ends_at'], unique=False)

    op.create_table(
        'contest_referrals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contest_id', sa.Integer(), nullable=False),
        sa.Column('invitee_id', sa.BigInteger(), nullable=False),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('was_member_before', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reminder_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['contest_id'], ['contests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contest_id', 'invitee_id', name='uq_contest_invitee'),
        sa.CheckConstraint('invitee_id != referrer_id', name='ck_no_self_referral')
    )
    op.create_index(op.f('ix_contest_referrals_contest_id'), 'contest_referrals', ['contest_id'], unique=False)
    op.create_index(op.f('ix_contest_referrals_invitee_id'), 'contest_referrals', ['invitee_id'], unique=False)
    op.create_index(op.f('ix_contest_referrals_referrer_id'), 'contest_referrals', ['referrer_id'], unique=False)
    op.create_index(op.f('ix_contest_referrals_status'), 'contest_referrals', ['status'], unique=False)
    op.create_index('ix_contest_referrer_status', 'contest_referrals', ['contest_id', 'referrer_id', 'status'], unique=False)
    op.create_index('ix_contest_status', 'contest_referrals', ['contest_id', 'status'], unique=False)

    op.create_table(
        'contest_referral_audits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contest_id', sa.Integer(), nullable=False),
        sa.Column('referral_id', sa.Integer(), nullable=True),
        sa.Column('invitee_id', sa.BigInteger(), nullable=False),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contest_referral_audits_contest_id'), 'contest_referral_audits', ['contest_id'], unique=False)
    op.create_index(op.f('ix_contest_referral_audits_invitee_id'), 'contest_referral_audits', ['invitee_id'], unique=False)
    op.create_index(op.f('ix_contest_referral_audits_referrer_id'), 'contest_referral_audits', ['referrer_id'], unique=False)


def downgrade() -> None:
    op.drop_table('contest_referral_audits')
    op.drop_table('contest_referrals')
    op.drop_table('contests')
