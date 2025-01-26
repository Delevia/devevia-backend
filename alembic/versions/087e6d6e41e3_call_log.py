""" call log

Revision ID: 087e6d6e41e3
Revises: 2bda3ddebfaa
Create Date: 2025-01-08 11:50:00.703964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '087e6d6e41e3'
down_revision: Union[str, None] = '2bda3ddebfaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('call_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ride_id', sa.Integer(), nullable=False),
    sa.Column('caller_id', sa.Integer(), nullable=False),
    sa.Column('receiver_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['caller_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ride_id'], ['rides.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_call_logs_id'), 'call_logs', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_call_logs_id'), table_name='call_logs')
    op.drop_table('call_logs')
    # ### end Alembic commands ###
