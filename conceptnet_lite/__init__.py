from pathlib import Path
from typing import Iterable, Optional

import peewee

from conceptnet_lite.db import CONCEPTNET_EDGE_COUNT, CONCEPTNET_DUMP_DOWNLOAD_URL, CONCEPTNET_DB_NAME
from conceptnet_lite.db import CONCEPTNET_DB_URL
from conceptnet_lite.db import Concept, Language, Label, Relation, RelationName, Edge
from conceptnet_lite.db import prepare_db, _open_db, _generate_db_path, download_db
from conceptnet_lite.utils import PathOrStr, _to_snake_case


def connect(
        db_path: PathOrStr = CONCEPTNET_DB_NAME,
        db_download_url: Optional[str] = CONCEPTNET_DB_URL,
        delete_compressed_db: bool = True,
        dump_download_url: str = CONCEPTNET_DUMP_DOWNLOAD_URL,
        load_dump_edge_count: int = CONCEPTNET_EDGE_COUNT,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
) -> None:
    """Connect to ConceptNet database.

    This function connects to ConceptNet database. If it does not exists, there are two options: to download ready
    database or to download the compressed ConceptNet dump, extract it, and load it
    into database (pass `db_download_url=None` for this option).

    Args:
        db_path: Path to the database.
        db_download_url: Link to compressed ConceptNet database. Pass `None` to build the db from dump.
        delete_compressed_db: Delete compressed database after extraction.
        dump_download_url: Link to compressed ConceptNet dump.
        load_dump_edge_count: Number of edges to load from the beginning of the dump file. Can be useful for testing.
        delete_compressed_dump: Delete compressed dump after unpacking.
        delete_dump: Delete dump after loading into database.
    """
    db_path = Path(db_path).expanduser().resolve()
    if db_path.is_dir():
        db_path = _generate_db_path(db_path)
    try:
        if db_path.is_file():
            _open_db(path=db_path)
        else:
            raise FileNotFoundError(2, "No such file", str(db_path))
    except FileNotFoundError:
        print(f"File not found: {db_path}")
        if db_download_url is not None:
            download_db(
                url=db_download_url,
                db_path=db_path,
                delete_compressed_db=delete_compressed_db,
            )
            _open_db(db_path)
        else:
            prepare_db(
                db_path=db_path,
                dump_download_url=dump_download_url,
                load_dump_edge_count=load_dump_edge_count,
                delete_compressed_dump=delete_compressed_dump,
                delete_dump=delete_dump,
            )


def edges_from(
        start_concepts: Iterable[Concept],
        relation: Optional[Relation] = None,
        same_language: bool = False,
) -> peewee.BaseModelSelect:
    start_concepts = list(start_concepts)
    result = Edge.select().where(Edge.start.in_(start_concepts))
    if relation is not None:
        result = result.where(Edge.relation == relation)
    if same_language:
        ConceptAlias = Concept.alias()
        result = (result
                  .join(ConceptAlias, on=(ConceptAlias.id == Edge.end))
                  .join(Label)
                  .join(Language)
                  .where(Language.id == start_concepts[0].label.language))
    return result


def edges_to(
        end_concepts: Iterable[Concept],
        relation: Optional[Relation] = None,
        same_language: bool = False,
) -> peewee.BaseModelSelect:
    end_concepts = list(end_concepts)
    result = Edge.select().where(Edge.end.in_(end_concepts))
    if relation is not None:
        result = result.where(Edge.relation == relation)
    if same_language:
        ConceptAlias = Concept.alias()
        result = (result
                  .join(ConceptAlias, on=(ConceptAlias.id == Edge.start))
                  .join(Label)
                  .join(Language)
                  .where(Language.id == end_concepts[0].label.language))
    return result


def edges_for(
        concepts: Iterable[Concept],
        relation: Optional[Relation] = None,
        same_language: bool = False,
) -> peewee.BaseModelSelect:
    return (edges_from(concepts, relation=relation, same_language=same_language)
            | edges_to(concepts, relation=relation, same_language=same_language))


def edges_between(
        start_concepts: Iterable[Concept],
        end_concepts: Iterable[Concept],
        relation: Optional[Relation] = None,
        two_way: bool = False,
) -> peewee.BaseModelSelect:
    condition = Edge.start.in_(start_concepts) & Edge.end.in_(end_concepts)
    if two_way:
        condition |= Edge.start.in_(end_concepts) & Edge.end.in_(start_concepts)
    if relation is not None:
        condition &= Edge.relation == relation
    return Edge.select().where(condition)
