"""Add profile and NIN photo fields to Rider

Revision ID: c94450fb918c
Revises: 57a0ac249180
Create Date: 2024-11-11 23:05:15.713334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c94450fb918c'
down_revision: Union[str, None] = '57a0ac249180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('riders', 'rider_photo',
               existing_type=postgresql.BYTEA(),
               type_=sa.String(),
               existing_nullable=True)
    op.alter_column('riders', 'nin_photo',
               existing_type=postgresql.BYTEA(),
               type_=sa.String(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('riders', 'nin_photo',
               existing_type=sa.String(),
               type_=postgresql.BYTEA(),
               existing_nullable=True)
    op.alter_column('riders', 'rider_photo',
               existing_type=sa.String(),
               type_=postgresql.BYTEA(),
               existing_nullable=True)
    # ### end Alembic commands ###
