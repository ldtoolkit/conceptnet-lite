import csv
import gzip
import json
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Generator, Tuple, Optional, Type

import langcodes
from pony import orm
from pySmartDL import SmartDL

from conceptnet_lite.db import db, EnumConverter, LanguageConverter, Concept, Language, Label, Relation, RelationName
from conceptnet_lite.db import Edge
from conceptnet_lite.utils import PathOrStr, to_snake_case


CONCEPTNET_DOWNLOAD_URL = 'https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz'


class ConceptNet:
    def __init__(
            self,
            path: PathOrStr,
            dump_dir_path: PathOrStr = Path.cwd(),
            download_missing_dump: bool = True,
            download_url: str = CONCEPTNET_DOWNLOAD_URL,
            download_progress_bar: bool = True,
            load_dump_to_db: bool = True,
            load_dump_edges_count: Optional[int] = None,
            delete_compressed_dump: bool = True,
            delete_dump: bool = True,
    ):
        def open_db(create_db: bool = False):
            db.bind(provider='sqlite', filename=str(self._db_path), create_db=create_db)
            db.provider.converter_classes += [(Enum, EnumConverter), (langcodes.Language, LanguageConverter)]
            db.generate_mapping(create_tables=True)

        self._db_path = Path(path).expanduser().resolve()
        dump_dir_path = Path(dump_dir_path).expanduser().resolve()

        if load_dump_to_db and not self._db_path.is_file():
            dump_path = dump_dir_path / Path(CONCEPTNET_DOWNLOAD_URL.rpartition('/')[-1]).with_suffix('')
            if download_missing_dump and not dump_path.is_file():
                self.download_and_unpack_dump(
                    url=download_url,
                    dir_path=dump_dir_path,
                    progress_bar=download_progress_bar,
                    delete_compressed_dump=delete_compressed_dump,
                )

            open_db(create_db=True)
            dump_loading_start = datetime.now()
            self.load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
            dump_loading_end = datetime.now()
            print("Time for loading dump:", dump_loading_end - dump_loading_start)
        else:
            open_db()

    @classmethod
    def download_and_unpack_dump(
            cls,
            url: str = CONCEPTNET_DOWNLOAD_URL,
            dir_path: PathOrStr = Path.cwd(),
            progress_bar: bool = True,
            delete_compressed_dump: bool = True,
    ):
        print("Download compressed dump")
        compressed_dump_downloader = SmartDL(url, str(dir_path), progress_bar=progress_bar)
        compressed_dump_path = Path(compressed_dump_downloader.dest)
        if not compressed_dump_path.is_file():
            shutil.rmtree(compressed_dump_path, ignore_errors=True)
            compressed_dump_downloader.start()
        print("Uncompress compressed dump")
        dump_path = Path(compressed_dump_path).with_suffix('')
        with gzip.open(str(compressed_dump_path), 'rb') as f_in:
            with open(str(dump_path), 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        if delete_compressed_dump:
            compressed_dump_path.unlink()

    @orm.db_session
    def load_dump_to_db(
            self,
            dump_path: PathOrStr,
            edges_count: Optional[int] = None,
            delete_dump: bool = True,
    ):
        def edges_from_dump_by_parts_generator(
                path: PathOrStr,
                count: Optional[int] = None,
        ) -> Generator[Tuple[str, str, str, str], None, None]:
            with open(str(path), newline='') as f:
                reader = csv.reader(f, delimiter='\t')
                for i, row in enumerate(reader):
                    yield row[1:5]
                    if i == count:
                        break

        def extract_relation_name(uri: str) -> str:
            return to_snake_case(uri.rpartition('/')[-1])

        def get_or_create(entity_cls: Type[db.Entity], **kwargs):
            return entity_cls.get(**kwargs) or entity_cls(**kwargs)

        def get_or_create_concept(uri: str) -> Concept:
            split_url = uri.split('/', maxsplit=4)
            language = get_or_create(Language, name=split_url[2])
            label = get_or_create(Label, text=split_url[3], language=language)
            concept = get_or_create(Concept, label=label, sense_label=('' if len(split_url) == 4 else split_url[4]))
            return concept

        print("Load dump to database")
        for relation_name, start_uri, end_uri, edge_etc_json in (
                edges_from_dump_by_parts_generator(path=dump_path, count=edges_count)):
            relation = get_or_create(Relation, name=RelationName(extract_relation_name(relation_name)))
            start = get_or_create_concept(uri=start_uri)
            end = get_or_create_concept(uri=end_uri)
            edge = get_or_create(Edge, relation=relation, start=start, end=end)
            edge.etc = json.loads(edge_etc_json)

        if delete_dump:
            dump_path.unlink()

    query = staticmethod(orm.db_session)
    select = staticmethod(orm.select)

    def edges_from(self, start_concepts, same_language: bool = True):
        return self.select(
            e for e in Edge
            if e.start in start_concepts and
            not same_language or e.start.label.language == e.end.label.language
        )

    def edges_to(self, end_concepts, same_language: bool = True):
        return self.select(
            e for e in Edge
            if e.end in end_concepts and
            not same_language or e.start.label.language == e.end.label.language
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
