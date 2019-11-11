import pytest

from conceptnet_lite import Label, Language, edges_for, edges_between, connect, Concept, Relation


@pytest.fixture(scope="session")
def _connect_to_conceptnet():
    connect("../../Python/conceptnet/conceptnet.db")


def test_concepts(_connect_to_conceptnet):
    russian = Language.get(name='ru')
    heaven_concepts = Label.get(text='рай', language=russian).concepts
    assert [i.uri for i in heaven_concepts] == ["/c/ru/рай", "/c/ru/рай/n"]


def test_one_way_relation(_connect_to_conceptnet):
    russian = Language.get(name='ru')
    heaven_concepts = Label.get(text='рай', language=russian).concepts
    hell_concepts = Label.get(text='ад', language=russian).concepts
    result = list(edges_between(heaven_concepts, hell_concepts, two_way=False))
    assert len(result) == 1 and result[0].relation.uri == Relation(name="antonym").uri


def test_two_ways_relation(_connect_to_conceptnet):
    russian = Language.get(name='ru')
    heaven_concepts = Label.get(text='рай', language=russian).concepts
    hell_concepts = Label.get(text='ад', language=russian).concepts
    result = list(edges_between(heaven_concepts, hell_concepts, two_way=True))
    assert len(result) == 2 and [i.relation.uri for i in result] == [Relation(name="antonym").uri,
                                                                     Relation(name="antonym").uri]
