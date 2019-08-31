from pathlib import Path

from conceptnet_lite.db import CONCEPTNET_EDGE_COUNT, CONCEPTNET_DOWNLOAD_URL
from conceptnet_lite.db import Concept, Language, Label, Relation, RelationName, Edge
from conceptnet_lite.db import prepare_db, open_db
from conceptnet_lite.utils import PathOrStr, to_snake_case


def connect(
        path: PathOrStr,
        dump_dir_path: PathOrStr = Path.cwd(),
        download_url: str = CONCEPTNET_DOWNLOAD_URL,
        download_progress_bar: bool = True,
        load_dump_edges_count: int = CONCEPTNET_EDGE_COUNT,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
):
    path = Path(path).expanduser().resolve()
    try:
        if not path.is_file():
            raise OSError(f"Database does not exists: {path}")
        open_db(path=path)
    except OSError as e:
        print(str(e))
        prepare_db(
            db_path=path,
            dump_dir_path=dump_dir_path,
            download_url=download_url,
            download_progress_bar=download_progress_bar,
            load_dump_edges_count=load_dump_edges_count,
            delete_compressed_dump=delete_compressed_dump,
            delete_dump=delete_dump,
        )


def edges_from(start_concepts):
    result = Edge.select().where(Edge.start.in_(start_concepts))
    return result


def edges_to(end_concepts):
    result = Edge.select().where(Edge.end.in_(end_concepts))
    return result


def edges_for(concepts):
    return edges_from(concepts) | edges_to(concepts)


def edges_between(start_concepts, end_concepts, two_way: bool = False):
    condition = Edge.start.in_(start_concepts) & Edge.end.in_(end_concepts)
    if two_way:
        condition |= Edge.start.in_(end_concepts) & Edge.end.in_(start_concepts)
    return Edge.select().where(condition)
