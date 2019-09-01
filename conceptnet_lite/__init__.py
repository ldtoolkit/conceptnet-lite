from pathlib import Path
from typing import Iterable

import peewee

from conceptnet_lite.db import CONCEPTNET_EDGE_COUNT, CONCEPTNET_DOWNLOAD_URL
from conceptnet_lite.db import Concept, Language, Label, Relation, RelationName, Edge
from conceptnet_lite.db import prepare_db, _open_db
from conceptnet_lite.utils import PathOrStr, _to_snake_case


def connect(
        db_path: PathOrStr,
        dump_dir_path: PathOrStr = '.',
        download_url: str = CONCEPTNET_DOWNLOAD_URL,
        load_dump_edge_count: int = CONCEPTNET_EDGE_COUNT,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
) -> None:
    """Connect to ConceptNet database.

    This function downloads the compressed ConceptNet dump, unpacks it, loads it into database, and connects to it.
    First three steps are optional, and are executed only if needed.

    Args:
        db_path: Path to the resulting database.
        dump_dir_path: Path to the dir, where to store compressed and uncompressed dumps.
        download_url: Link to compressed ConceptNet dump.
        load_dump_edge_count: Number of edges to load from the beginning of the dump file. Can be useful for testing.
        delete_compressed_dump: Delete compressed dump after unpacking.
        delete_dump: Delete dump after loading into database.
    """
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.is_file():
        print(f"Database does not exist: {db_path}")
        prepare_db(
            db_path=db_path,
            dump_dir_path=dump_dir_path,
            download_url=download_url,
            load_dump_edge_count=load_dump_edge_count,
            delete_compressed_dump=delete_compressed_dump,
            delete_dump=delete_dump,
        )
    else:
        _open_db(path=db_path)


def edges_from(start_concepts: Iterable[Concept], same_language: bool = False) -> peewee.BaseModelSelect:
    if same_language:
        ConceptAlias = Concept.alias()
        start_concepts = list(start_concepts)
        return (Edge
                .select()
                .join(Concept, on=(Concept.id == Edge.start))
                .where(Concept.id.in_(start_concepts))
                .switch(Edge)
                .join(ConceptAlias, on=(ConceptAlias.id == Edge.end))
                .join(Label)
                .join(Language)
                .where(Language.id == start_concepts[0].label.language))
    else:
        return Edge.select().where(Edge.start.in_(start_concepts))


def edges_to(end_concepts: Iterable[Concept], same_language: bool = False) -> peewee.BaseModelSelect:
    if same_language:
        ConceptAlias = Concept.alias()
        end_concepts = list(end_concepts)
        return (Edge
                .select()
                .join(Concept, on=(Concept.id == Edge.end))
                .where(Concept.id.in_(end_concepts))
                .switch(Edge)
                .join(ConceptAlias, on=(ConceptAlias.id == Edge.start))
                .join(Label)
                .join(Language)
                .where(Language.id == end_concepts[0].label.language))
    else:
        return Edge.select().where(Edge.end.in_(end_concepts))


def edges_for(concepts: Iterable[Concept], same_language: bool = False) -> peewee.BaseModelSelect:
    return edges_from(concepts, same_language=same_language) | edges_to(concepts, same_language=same_language)


def edges_between(
        start_concepts: Iterable[Concept],
        end_concepts: Iterable[Concept],
        two_way: bool = False,
) -> peewee.BaseModelSelect:
    condition = Edge.start.in_(start_concepts) & Edge.end.in_(end_concepts)
    if two_way:
        condition |= Edge.start.in_(end_concepts) & Edge.end.in_(start_concepts)
    return Edge.select().where(condition)
