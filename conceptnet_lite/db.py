import csv
import gzip
import shutil
import struct
from pathlib import Path
from typing import Optional, Generator, Tuple
from uuid import uuid4

import langcodes
import lmdb
import pony.orm.dbapiprovider
from pony import orm
from pySmartDL import SmartDL

from conceptnet_lite.utils import PathOrStr, to_snake_case


class RelationName:
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


class LanguageConverter(orm.dbapiprovider.StrConverter):
    def validate(self, val, obj=None):
        val = langcodes.Language.get(val)
        if not isinstance(val, langcodes.Language):
            raise ValueError('Must be an langcodes.Language. Got {}'.format(type(val)))
        return val

    def py2sql(self, val: langcodes.Language):
        return str(val)

    def sql2py(self, value):
        return langcodes.Language.get(value)


db = orm.Database()


class Relation(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(str, unique=True)
    edges = orm.Set('Edge')

    @property
    def uri(self) -> str:
        return f'/r/{self.name}'


class Concept(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    edges_out = orm.Set('Edge', reverse='start')
    edges_in = orm.Set('Edge', reverse='end')
    label = orm.Required('Label')
    sense_label = orm.Optional(str)

    @property
    def uri(self) -> str:
        ending = f'/{self.sense_label}' if self.sense_label else ''
        return f'/c/{self.label.language.name}/{self.label.text}{ending}'

    @property
    def language(self) -> 'Language':
        return self.label.language

    @property
    def text(self) -> str:
        return self.label.text


class Edge(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    relation = orm.Required(Relation)
    start = orm.Required(Concept, reverse='edges_out')
    end = orm.Required(Concept, reverse='edges_in')
    etc = orm.Optional(orm.Json)

    @property
    def uri(self) -> str:
        return f'/a/[{self.relation.uri}/,{self.start.uri}/,{self.end.uri}/]'


class Language(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(langcodes.Language)
    labels = orm.Set('Label')


class Label(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    text = orm.Required(str, index=True)
    language = orm.Required(Language)
    concepts = orm.Set(Concept)


def open_db(path: PathOrStr):
    db.bind(provider='sqlite', filename=str(path), create_db=True)
    db.provider.converter_classes.append((langcodes.Language, LanguageConverter))
    db.generate_mapping(create_tables=True)


CONCEPTNET_DOWNLOAD_URL = 'https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz'


def download_dump(
    url: str = CONCEPTNET_DOWNLOAD_URL,
    dir_path: PathOrStr = Path.cwd(),
    progress_bar: bool = True,
):
    print("Download compressed dump")
    compressed_dump_downloader = SmartDL(url, str(dir_path), progress_bar=progress_bar)
    compressed_dump_path = Path(compressed_dump_downloader.dest)
    if not compressed_dump_path.is_file():
        shutil.rmtree(str(compressed_dump_path), ignore_errors=True)
        compressed_dump_downloader.start()


def unpack_dump(
    compressed_dump_path: PathOrStr,
    delete_compressed_dump: bool = True,
):
    print("Uncompress compressed dump")
    dump_path = Path(compressed_dump_path).with_suffix('')
    with gzip.open(str(compressed_dump_path), 'rb') as f_in:
        with open(str(dump_path), 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    if delete_compressed_dump:
        compressed_dump_path.unlink()


def load_dump_to_db(
    dump_path: PathOrStr,
    edges_count: Optional[int] = None,
    delete_dump: bool = True,
):
    def edges_from_dump_by_parts_generator(
            count: Optional[int] = None,
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        with open(str(dump_path), newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for i, row in enumerate(reader):
                yield row[1:5]
                if i == count:
                    break

    def extract_relation_name(uri: str) -> str:
        return to_snake_case(uri[3:])

    def get_struct_format(length: int) -> str:
        return f'{length}Q'

    def pack_ints(*ints) -> bytes:
        return struct.pack(get_struct_format(length=len(ints)), *ints)

    def unpack_ints(buffer: bytes) -> Tuple[int, ...]:
        return struct.unpack(get_struct_format(len(buffer) // 8), buffer)

    def relation_in_bytes(relation_uri: str) -> bytes:
        relation_name = extract_relation_name(relation_uri)
        return relation_name.encode('utf8')

    def language_and_label_in_bytes(concept_uri: str) -> Tuple[bytes, bytes]:
        return tuple(x.encode('utf8') for x in concept_uri.split('/', maxsplit=4)[2:4])[:2]

    def normalize() -> None:
        def normalize_relation() -> None:
            nonlocal relation_i

            relation_b = relation_in_bytes(relation_uri=relation_uri)
            relation_exists = txn.get(relation_b, db=relation_db) is not None
            if not relation_exists:
                relation_i += 1
                relation_i_b = pack_ints(relation_i)
                txn.put(relation_b, relation_i_b, db=relation_db)

        def normalize_concept(uri: str) -> None:
            nonlocal language_i, label_i, concept_i

            language_b, label_b = language_and_label_in_bytes(concept_uri=uri)

            language_id_b = txn.get(language_b, db=language_db)
            if language_id_b is None:
                language_i += 1
                language_id_b = pack_ints(language_i)
                txn.put(language_b, language_id_b, db=language_db)

            label_language_b = label_b + b'/' + language_b
            label_id_b = txn.get(label_language_b, db=label_db)
            if label_id_b is None:
                label_i += 1
                label_id_b = pack_ints(label_i)
                txn.put(label_language_b, label_id_b, db=label_db)

            concept_b = uri.encode('utf8')
            concept_id_b = txn.get(concept_b, db=concept_db)
            if concept_id_b is None:
                concept_i += 1
                concept_id_b = pack_ints(concept_i)
                txn.put(concept_b, concept_id_b, db=concept_db)

        print('Dump normalization')
        language_i, relation_i, label_i, concept_i, edge_i = 5 * [0]
        for relation_uri, start_uri, end_uri, _ in edges_from_dump_by_parts_generator(count=edges_count):
            edge_i += 1

            normalize_relation()
            normalize_concept(start_uri)
            normalize_concept(end_uri)

            if edge_i % 1000000 == 0:
                print(edge_i)

    def insert() -> None:
        def insert_objects_from_edge():
            nonlocal edge_i

            def insert_relation() -> int:
                nonlocal relation_i

                relation_b = relation_in_bytes(relation_uri=relation_uri)
                result_id, = unpack_ints(buffer=txn.get(relation_b, db=relation_db))
                if result_id == relation_i:
                    name = relation_b.decode('utf8')
                    cursor.execute('insert into Relation (name) values (?)', (name, ))
                    relation_i += 1
                return result_id

            def insert_concept(uri: str) -> int:
                nonlocal language_i, label_i, concept_i

                split_uri = uri.split('/', maxsplit=4)

                language_b, label_b = language_and_label_in_bytes(concept_uri=uri)

                language_id, = unpack_ints(buffer=txn.get(language_b, db=language_db))
                if language_id == language_i:
                    name = split_uri[2]
                    cursor.execute('insert into Language (name) values (?)', (name, ))
                    language_i += 1

                label_language_b = label_b + b'/' + language_b
                label_id, = unpack_ints(buffer=txn.get(label_language_b, db=label_db))
                if label_id == label_i:
                    text = split_uri[3]
                    params = (text, language_id)
                    cursor.execute('insert into Label (text, language) values (?, ?)', params)
                    label_i += 1

                concept_b = uri.encode('utf8')
                concept_id, = unpack_ints(buffer=txn.get(concept_b, db=concept_db))
                if concept_id == concept_i:
                    sense_label = '' if len(split_uri) == 4 else split_uri[4]
                    params = (label_id, sense_label)
                    cursor.execute('insert into Concept (label, sense_label) values (?, ?)', params)
                    concept_i += 1
                return concept_id

            def insert_edge() -> None:
                params = (relation_id, start_id, end_id, edge_etc)
                cursor.execute('insert into Edge (relation, start, end, etc) values (?, ?, ?, ?)', params)

            relation_id = insert_relation()
            start_id = insert_concept(uri=start_uri)
            end_id = insert_concept(uri=end_uri)
            insert_edge()
            edge_i += 1

        print('Dump insertion')
        relation_i, language_i, label_i, concept_i, edge_i = 5 * [1]
        edges = edges_from_dump_by_parts_generator(count=edges_count)
        finished = False
        while not finished:
            edge_count_per_insert = 1000000
            with orm.db_session:
                db_connection = db.get_connection()
                cursor = db_connection.cursor()
                for _ in range(edge_count_per_insert):
                    try:
                        relation_uri, start_uri, end_uri, edge_etc = next(edges)
                    except StopIteration:
                        finished = True
                        break
                    insert_objects_from_edge()
                pass
            pass

    GIB = 1 << 30
    lmdb_db_path = dump_path.parent / f'conceptnet-lmdb-{uuid4()}.db'
    env = lmdb.open(str(lmdb_db_path), map_size=4*GIB, max_dbs=5, sync=False, writemap=False)
    relation_db = env.open_db(b'relation')
    language_db = env.open_db(b'language')
    label_db = env.open_db(b'label')
    concept_db = env.open_db(b'concept')
    with env.begin(write=True) as txn:
        normalize()
        insert()

    shutil.rmtree(str(lmdb_db_path), ignore_errors=True)
    if delete_dump:
        dump_path.unlink()


def prepare_db(
        db_path: PathOrStr,
        dump_dir_path: PathOrStr = Path.cwd(),
        download_url: str = CONCEPTNET_DOWNLOAD_URL,
        download_progress_bar: bool = True,
        load_dump_edges_count: Optional[int] = None,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
):
    db_path = Path(db_path).expanduser().resolve()
    dump_dir_path = Path(dump_dir_path).expanduser().resolve()
    compressed_dump_path = dump_dir_path / Path(CONCEPTNET_DOWNLOAD_URL.rpartition('/')[-1])
    dump_path = compressed_dump_path.with_suffix('')

    db_path.parent.mkdir(parents=True, exist_ok=True)
    dump_dir_path.mkdir(parents=True, exist_ok=True)

    open_db(path=db_path)

    try:
        load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
    except FileNotFoundError as e:
        print(str(e).replace('[Errno 2] ', '', 1))
        try:
            unpack_dump(compressed_dump_path=compressed_dump_path, delete_compressed_dump=delete_compressed_dump)
            load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
        except FileNotFoundError as e:
            print(str(e).replace('[Errno 2] ', '', 1))
            download_dump(url=download_url, dir_path=dump_dir_path, progress_bar=download_progress_bar)
            unpack_dump(compressed_dump_path=compressed_dump_path, delete_compressed_dump=delete_compressed_dump)
            load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
