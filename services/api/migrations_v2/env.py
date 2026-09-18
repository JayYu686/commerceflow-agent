from alembic import context
from sqlalchemy import create_engine, pool

from commerceflow.config import settings
from commerceflow.models import Base, CommerceBase

commerce = context.get_x_argument(as_dictionary=True).get("database") == "commerce"
url = settings().commerce_database_url if commerce else settings().database_url
metadata = CommerceBase.metadata if commerce else Base.metadata
if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5}).connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
