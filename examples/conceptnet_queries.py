from pathlib import Path

import conceptnet_lite
from conceptnet_lite import Label, Language, edges_for, edges_between


base_dir_path = Path('~/conceptnet-lite-data')
conceptnet_lite.connect(
    path=base_dir_path / 'conceptnet.db',
    dump_dir_path=base_dir_path,
)

russian = Language.get(name='ru')

print("All edges between 'рай' и 'ад':")
heaven_concepts = Label.get(text='рай', language=russian).concepts
hell_concepts = Label.get(text='ад', language=russian).concepts
for e in edges_between(heaven_concepts, hell_concepts, two_way=True):
    print("  Edge URI:", e.uri)
    print("  Relation:", e.relation.name)

english = Language.get(name='en')

print("Get edges for 'introvert':")
introvert_concepts = Label.get(text='introvert', language=english).concepts
for e in edges_for(introvert_concepts):
    print("  Edge URI:", e.uri)

print("Traversing Russian:")
for l in russian.labels:
    print("  Label:", l.text)
    for c in l.concepts:
        print("    Concept URI:", c.uri)
        print("    Concept language:", c.language.name)
        if c.edges_out:
            print("      Edges out:")
            for e in c.edges_out:
                print("        Edge URI:", e.uri)
                print("        Relation:", e.relation.name)
                print("        End:", e.end.uri)
        if c.edges_in:
            print("      Edges in:")
            for e in c.edges_in:
                print("        Edge URI:", e.uri)
                print("        Relation:", e.relation.name)
                print("        End:", e.end.uri)
