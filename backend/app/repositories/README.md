# Repository layer

Repositories own SQLAlchemy queries and receive an `AsyncSession` from their caller.
They flush changes so generated identifiers and constraint errors are available,
but do not commit; transaction boundaries belong to the service or request scope.
Use the named repositories for domain queries and `BaseRepository` for common
entity CRUD. Repositories must not call LLMs or contain HTTP behavior.
