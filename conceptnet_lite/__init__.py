from pathlib import Path
from typing import Optional

from pony import orm

from conceptnet_lite.db import db, LanguageConverter, Concept, Language, Label, Relation, RelationName, open_db
from conceptnet_lite.db import CONCEPTNET_DOWNLOAD_URL, prepare_db, Edge
from conceptnet_lite.utils import PathOrStr, to_snake_case


class ConceptNet:
    def __init__(
            self,
            path: PathOrStr,
            dump_dir_path: PathOrStr = Path.cwd(),
            download_url: str = CONCEPTNET_DOWNLOAD_URL,
            download_progress_bar: bool = True,
            load_dump_edges_count: Optional[int] = None,
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

    query = staticmethod(orm.db_session)
    select = staticmethod(orm.select)

    def edges_from(self, start_concepts, same_language: bool = True):
        return self.select(
            e for e in Edge
            if (e.start in start_concepts) and
            (not same_language or e.start.label.language == e.end.label.language)
        )

    def edges_to(self, end_concepts, same_language: bool = True):
        return self.select(
            e for e in Edge
            if (e.end in end_concepts) and
            (not same_language or e.start.label.language == e.end.label.language)
        )

    def edges_for(self, concepts, same_language: bool = True):
        return self.select(
            e for e in Edge
            if (e.start in concepts or e.end in concepts) and
            (not same_language or e.start.label.language == e.end.label.language)
        )

    def edges_between(self, start_concepts, end_concepts, two_way: bool = False):
        if two_way:
            return self.select(e for e in Edge if (
                    ((e.start in start_concepts) and (e.end in end_concepts)) or
                    ((e.start in end_concepts) and (e.end in start_concepts))))
        else:
            return self.select(e for e in Edge if (
                    (e.start in start_concepts) and (e.end in end_concepts)))
