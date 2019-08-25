from conceptnet_lite import ConceptNet, Label, Language

cn = ConceptNet(
    path='~/conceptnet-lite-data/conceptnet.db',
    dump_dir_path='~/conceptnet-lite-data',
    load_dump_edges_count=100000,
    delete_dump=False,
)
with cn.query():
    print("Traversing Russian:")
    russian = Language.get(name='ru')
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

    print("All edges between 'рай' и 'ад':")
    heaven_concepts = Label.get(text='рай').concepts
    hell_concepts = Label.get(text='ад').concepts
    for e in cn.edges_between(heaven_concepts, hell_concepts, two_way=True):
        print("  Edge URI:", e.uri)
        print("  Relation:", e.relation.name)

    print("Get edges for 'introvert':")
    english = Language.get(name='en')
    for e in cn.edges_for(Label.get(text='introvert', language=english).concepts):
        print("  Edge URI:", e.uri)
