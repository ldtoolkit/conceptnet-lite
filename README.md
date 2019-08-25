# conceptnet-lite

Conceptnet-lite is a Python library for working with ConceptNet offline without the need for PostgreSQL.

The basic usage is as follows. 

## Loading the database object

ConceptNet releases happen once a year. You can build your own database from an assertions file, but if there is a pre-built file it will be faster to just download that one. Here is the [database file](todo) for ConceptNet 5.7 release. 

```python
from conceptnet_lite import ConceptNet, Label, Language

cn = ConceptNet(path='/path/to/conceptnet.db')
```

## Building the database for a new release.

The assertion files for ConceptNet are provided [here](https://github.com/commonsense/conceptnet5/wiki/Downloads). 

(building instructions TBA)

The structure of the resulting database is shown [here](https://github.com/ldtoolkit/conceptnet-lite/blob/master/docs/er-diagram.pdf) 

## Accessing concepts

To work with the ConceptNet database you will need to use the `.query()` context manager, which enables the [database sessions](https://docs.ponyorm.org/transactions.html#working-with-db-session). All operations with the database need to be performed inside the `with cn.query():` context.

Concepts objects are created by looking for every entry that matches the input string exactly. If none is found, the concepts object will be returned as `None`. 

```python
with cn.query():
    cat_concepts = Label.get(text='cat').concepts  #
    for c in cat_concepts:
        print("    Concept URI:", c.uri)
        print("    Concept text:", c.text) 
```

`concept.uri` provides access to ConceptNet URIs, as described [here](https://github.com/commonsense/conceptnet5/wiki/URI-hierarchy). You can also retrieve only the text of the entry by `concept.text`.

## Working with languages

You can limit the languages to search for matches. Label.get() takes an optional `language` attribute that is expected to be a language object created by the [langcodes library](https://github.com/LuminosoInsight/langcodes).

```python
with cn.query():
    english = Language.get(name='en')
    cat_concepts = Label.get(text='cat', language=english).concepts  #
    for c in cat_concepts:
        print("    Concept URI:", c.uri)
        print("    Concept text:", c.text) 
        print("    Concept language:", c.language.name)
```

## Querying edges between concepts

To retrieve the set of relations between two concepts, you need to create the concept objects (optionally specifying the language as described above). `cn.edges_between()` method retrieves all edges between the specified concepts. You can access its URI and a number of attributes, as shown below.

Some ConceptNet relations are symmetrical: for example, the antonymy between *white* and *black* works both ways. Some relations are asymmetrical: e.g. the relation between *cat* and *mammal* is either hyponymy or hyperonymy, depending on the direction. The `two_way` argument lets you choose whether the query should be symmetrical or not.

```python
with cn.query():
    english = Language.get(name='en')
    introvert_concepts = Label.get(text='introvert', language=english).concepts
    extrovert_concepts = Label.get(text='extrovert', language=english).concepts
    for e in cn.edges_between(introvert_concepts, extrovert_concepts,
    two_way=False):
        print("  Edge URI:", e.uri)
        print(e.relation.name, e.start.text, e.end.text, e.etc)
```
* **e.relation.name**: the name of ConceptNet relation. Full list [here](https://github.com/commonsense/conceptnet5/wiki/Relations).

* **e.start.text, e.end.text**: the source and the target concepts in the edge

* **e.etc**: the ConceptNet [metadata](https://github.com/commonsense/conceptnet5/wiki/Edges) dictionary contains the source dataset, sources, weight, and license. For example, the introvert:extrovert edge for English contains the following metadata:

```
{
	'dataset': '/d/wiktionary/en',
	'license': 'cc:by-sa/4.0',
	'sources': [{
		'contributor': '/s/resource/wiktionary/en',
		'process': '/s/process/wikiparsec/2'
	}, {
		'contributor': '/s/resource/wiktionary/fr',
		'process': '/s/process/wikiparsec/2'
	}],
	'weight': 2.0
}
```

## Accessing all relations for a given concept

You can also retrieve all relations between a given concept and all other concepts, with the same options as above:

```python
with cn.query():
    english = Language.get(name='en')
    for e in cn.edges_for(Label.get(text='introvert', language=english, same_language=True).concepts):
        print("  Edge URI:", e.uri)
        print(e.relation.name, e.start.text, e.end.text, e.etc)
```

The only difference is that since the other concepts are not specified, it is possible to get edges to concepts in languages other than the source concept language. By default this option is off, but if you need to retrieve, say, Chinese antonyms of an English word, you can set `same_language=False`.

## Accessing concept edges with a given relation direction

You can also query the relations that have a specific concept as target or source. This is achieved with `concept.edges_out` and `concept.edges_in`, as follows:

```python
with cn.query():
    english = Language.get(name='en')
    cat_concepts = Label.get(text='introvert', language=english).concepts  #
    for c in cat_concepts:
        print("    Concept text:", c.text) # shall we also contract this to c.text?
        if c.edges_out:
            print("      Edges out:")
            for e in c.edges_out:
                print("        Edge URI:", e.uri)
                print("        Relation:", e.relation.name)
                print("        End:", e.end.text)
        if c.edges_in:
            print("      Edges in:")
            for e in c.edges_in:
                print("        Edge URI:", e.uri)
                print("        Relation:", e.relation.name)
                print("        End:", e.end.text)
```


# Traversing all the data for a language
 
You can go over all concepts for a given language. For illustration, let us try Avestan, a "small" language with the code "ae" and vocab size of 371, according to the [ConceptNet language statistics](https://github.com/commonsense/conceptnet5/wiki/Languages). 
 
```python
with cn.query():
    mylanguage = Language.get(name='ae')
    for l in mylanguage.labels:
        print("  Label:", l.text)
        for c in l.concepts:
            print("    Concept URI:", c.uri)
            if c.edges_out:
                print("      Edges out:")
                for e in c.edges_out:
                    print("        Edge URI:", e.uri)
            if c.edges_in:
                print("      Edges in:")
                for e in c.edges_in:
                    print("        Edge URI:", e.uri)
```

Todo:

- [ ] add database file link 
- [ ] describe how to build the database
- [ ] add sample outputs