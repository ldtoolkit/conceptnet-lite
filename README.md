# conceptnet-lite

Conceptnet-lite is a Python library for working with ConceptNet offline without the need for PostgreSQL.

The library comes with Apache License 2.0, and is separate from ConceptNet itself. The ConceptNet is available under [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/) license, which also applies to the formatted database file that we provide. See [here](https://github.com/commonsense/conceptnet5/wiki/Copying-and-sharing-ConceptNet) for the list of conditions for using ConceptNet data.

This is the official citation for ConceptNet if you use it in research:

> Robyn Speer, Joshua Chin, and Catherine Havasi. 2017. "ConceptNet 5.5: An Open Multilingual Graph of General Knowledge." In proceedings of AAAI 31.

The basic usage of `conceptnet-lite` library is as follows.

## Loading the database object

ConceptNet releases happen once a year. You can use `conceptnet-lite` to build your own database from the raw assertions file, but if there is a pre-built file it will be faster to just download that one. Here is the [compressed database file](todo) for ConceptNet 5.7 release.

```python
import conceptnet_lite

conceptnet_lite.connect('/path/to/conceptnet.db')
```

## Building the database for a new release.

If you provide an empty directory, `conceptnet-lite` will attempt to download the raw assertions file from [here](https://github.com/commonsense/conceptnet5/wiki/Downloads) and build the database. This takes several hours, so we recommend getting the pre-built file.

```python
import conceptnet_lite

conceptnet_lite.connect('/empty/path/')
```

## Accessing concepts

Concepts objects are created by looking for every entry that matches the input string exactly.
If none is found, the `peewee.DoesNotExist` exception will be raised.

```python
from conceptnet_lite import Label

cat_concepts = Label.get(text='cat').concepts  #
for c in cat_concepts:
    print("    Concept URI:", c.uri)
    print("    Concept text:", c.text)
```

`concept.uri` provides access to ConceptNet URIs, as described [here](https://github.com/commonsense/conceptnet5/wiki/URI-hierarchy). You can also retrieve only the text of the entry by `concept.text`.

## Working with languages

You can limit the languages to search for matches. Label.get() takes an optional `language` attribute that is expected to be an instance `Language`, which in turn is created by calling `Language.get()` with `name` argument.
List of available languages and their codes are described [here](https://github.com/commonsense/conceptnet5/wiki/Languages).

```python
from conceptnet_lite import Label, Language

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
from conceptnet_lite import Label, Language, edges_between

english = Language.get(name='en')
introvert_concepts = Label.get(text='introvert', language=english).concepts
extrovert_concepts = Label.get(text='extrovert', language=english).concepts
for e in edges_between(introvert_concepts, extrovert_concepts, two_way=False):
    print("  Edge URI:", e.uri)
    print(e.relation.name, e.start.text, e.end.text, e.etc)
```
* **e.relation.name**: the name of ConceptNet relation. Full list [here](https://github.com/commonsense/conceptnet5/wiki/Relations).

* **e.start.text, e.end.text**: the source and the target concepts in the edge

* **e.etc**: the ConceptNet [metadata](https://github.com/commonsense/conceptnet5/wiki/Edges) dictionary contains the source dataset, sources, weight, and license. For example, the introvert:extrovert edge for English contains the following metadata:

```json
{
	"dataset": "/d/wiktionary/en",
	"license": "cc:by-sa/4.0",
	"sources": [{
		"contributor": "/s/resource/wiktionary/en",
		"process": "/s/process/wikiparsec/2"
	}, {
		"contributor": "/s/resource/wiktionary/fr",
		"process": "/s/process/wikiparsec/2"
	}],
	"weight": 2.0
}
```

## Accessing all relations for a given concepts

You can also retrieve all relations between a given concepts and all other concepts, with the same options as above:

```python
from conceptnet_lite import Label, Language, edges_for

english = Language.get(name='en')
for e in edges_for(Label.get(text='introvert', language=english).concepts, same_language=True):
    print("  Edge URI:", e.uri)
    print(e.relation.name, e.start.text, e.end.text, e.etc)
```

Note that we have used optional argument `same_language=True`. By supplying this argument we make `edges_for` return
relations, both ends of which are in the same language. If this argument is skipped it is possible to get edges to
concepts in languages other than the source concepts language.

## Accessing concept edges with a given relation direction

You can also query the relations that have a specific concept as target or source. This is achieved with `concept.edges_out` and `concept.edges_in`, as follows:

```python
from conceptnet_lite import Language, Label

english = Language.get(name='en')
cat_concepts = Label.get(text='introvert', language=english).concepts  #
for c in cat_concepts:
    print("    Concept text:", c.text)
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
from conceptnet_lite import Language

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
