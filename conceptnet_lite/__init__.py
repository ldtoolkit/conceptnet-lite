import csv
import gzip
import shutil
from enum import Enum
from pathlib import Path
from typing import Generator, Tuple, Optional, List

from pySmartDL import SmartDL

from conceptnet_lite.graphdb_wrapper import GraphDb
from conceptnet_lite.utils import PathOrStr, to_snake_case


CONCEPTNET_DOWNLOAD_URL = 'https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz'


class RelationType(Enum):
    RELATED_TO = 'related_to'
    FORM_OF = 'form_of'
    IS_A = 'is_a'
    PART_OF = 'part_of'
    HAS_A = 'has_a'
    USED_FOR = 'used_for'
    CAPABLE_OF = 'capable_of'
    AT_LOCATION = 'at_location'
    CAUSES = 'causes'
    HAS_SUBEVENT = 'has_subevent'
    HAS_FIRST_SUBEVENT = 'has_first_subevent'
    HAS_LAST_SUBEVENT = 'has_last_subevent'
    HAS_PREREQUISITE = 'has_prerequisite'
    HAS_PROPERTY = 'has_property'
    MOTIVATED_BY_GOAL = 'motivated_by_goal'
    OBSTRUCTED_BY = 'obstructed_by'
    DESIRES = 'desires'
    CREATED_BY = 'created_by'
    SYNONYM = 'synonym'
    ANTONYM = 'antonym'
    DISTINCT_FROM = 'distinct_from'
    DERIVED_FROM = 'derived_from'
    SYMBOL_OF = 'symbol_of'
    DEFINED_AS = 'defined_as'
    MANNER_OF = 'manner_of'
    LOCATED_NEAR = 'located_near'
    HAS_CONTEXT = 'has_context'
    SIMILAR_TO = 'similar_to'
    ETYMOLOGICALLY_RELATED_TO = 'etymologically_related_to'
    ETYMOLOGICALLY_DERIVED_FROM = 'etymologically_derived_from'
    CAUSES_DESIRE = 'causes_desire'
    MADE_OF = 'made_of'
    RECEIVES_ACTION = 'receives_action'
    EXTERNAL_URL = 'external_url'


class Concept:
    def __init__(self, conceptnet: 'ConceptNet', url: str):
        self._conceptnet = conceptnet
        self._url = url

    def __str__(self):
        return self._url

    @property
    def antonyms(self) -> List['Concept']:
        return self._conceptnet.find(self, RelationType.ANTONYM)


class ConceptNet:
    def __init__(
            self,
            path: PathOrStr,
            dump_dir_path: PathOrStr = Path.cwd(),
            download_missing_dump: bool = True,
            download_url: str = CONCEPTNET_DOWNLOAD_URL,
            download_progress_bar: bool = True,
            load_dump_to_db: bool = True,
            load_dump_relations_count: Optional[int] = None,
            delete_compressed_dump: bool = True,
            delete_dump: bool = True,
    ):
        path = Path(path).expanduser()
        dump_dir_path = Path(dump_dir_path).expanduser()

        if load_dump_to_db and not path.is_file():
            dump_path = dump_dir_path / Path(CONCEPTNET_DOWNLOAD_URL.rpartition('/')[-1]).with_suffix('')
            if download_missing_dump and not dump_path.is_file():
                self.download_and_unpack_dump(
                    url=download_url,
                    dir_path=dump_dir_path,
                    progress_bar=download_progress_bar,
                    delete_compressed_dump=delete_compressed_dump,
                )
            self.load_dump_to_db(
                dump_path=dump_path,
                db_path=path,
                relations_count=load_dump_relations_count,
                delete_dump=delete_dump,
            )
        self._db = GraphDb(path=str(path))

    @staticmethod
    def _relations_from_dump_generator(
            path: PathOrStr,
            count: Optional[int] = None,
    ) -> Generator[Tuple[str, str, str], None, None]:
        i = 0
        with open(str(path), newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                yield row[2], _extract_relation_name(row[1]), row[3]
                i += 1
                if i == count:
                    break

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

    def load_dump_to_db(
            self,
            dump_path: PathOrStr,
            db_path: PathOrStr,
            relations_count: Optional[int] = None,
            delete_dump: bool = True,
    ):
        print("Load dump to database")
        self._db = GraphDb(path=str(db_path))
        relations_generator = self._relations_from_dump_generator(path=dump_path, count=relations_count)
        self._db.store_relations(relations=relations_generator)
        self._db.close()
        if delete_dump:
            dump_path.unlink()

    def relations_between(self, x: str, y: str) -> List[RelationType]:
        return [RelationType(relation_type) for relation_type in self._db.relations_between(x, y)]

    def find(self, source: Concept, relation_type: RelationType) -> List[Concept]:
        url_list = list(self._db.find(str(source), relation=relation_type.value))
        return [Concept(self, url) for url in url_list]

    def __getitem__(self, item: str) -> Concept:
        return Concept(conceptnet=self, url=self._db[item].to(list)[0])


def _extract_relation_name(url: str) -> str:
    return to_snake_case(url.rpartition('/')[-1])
