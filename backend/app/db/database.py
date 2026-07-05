from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .schema import Base

DATABASE_URL = "sqlite+aiosqlite:///./shopping.db"

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# FTS5 external-content table: mirrors products(name,description,brand) for full-text search
# without duplicating storage. Triggers keep it in sync on write.
FTS_STATEMENTS = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
        name, description, brand, content='products', content_rowid='id'
    )""",
    """CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products BEGIN
        INSERT INTO products_fts(rowid, name, description, brand) VALUES (new.id, new.name, new.description, new.brand);
    END""",
    """CREATE TRIGGER IF NOT EXISTS products_ad AFTER DELETE ON products BEGIN
        INSERT INTO products_fts(products_fts, rowid, name, description, brand) VALUES ('delete', old.id, old.name, old.description, old.brand);
    END""",
    """CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products BEGIN
        INSERT INTO products_fts(products_fts, rowid, name, description, brand) VALUES ('delete', old.id, old.name, old.description, old.brand);
        INSERT INTO products_fts(rowid, name, description, brand) VALUES (new.id, new.name, new.description, new.brand);
    END""",
]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in FTS_STATEMENTS:
            await conn.exec_driver_sql(statement)
