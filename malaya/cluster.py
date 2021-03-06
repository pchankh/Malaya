from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.manifold import MDS
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from .texts.vectorizer import SkipGramVectorizer
from .stem import sastrawi
from .texts._text_functions import (
    simple_textcleaning,
    split_into_sentences,
    STOPWORDS,
)

import numpy as np
import re
import random

_accepted_pos = [
    'ADJ',
    'ADP',
    'ADV',
    'AUX',
    'CCONJ',
    'DET',
    'NOUN',
    'NUM',
    'PART',
    'PRON',
    'PROPN',
    'SCONJ',
    'SYM',
    'VERB',
    'X',
]
_accepted_entities = [
    'OTHER',
    'law',
    'location',
    'organization',
    'person',
    'quantity',
    'time',
    'event',
    'X',
]


def cluster_words(list_words):
    """
    cluster similar words based on structure, eg, ['mahathir mohamad', 'mahathir'] = ['mahathir mohamad']

    Parameters
    ----------
    list_words : list of str

    Returns
    -------
    string: list of clustered words
    """
    if not isinstance(list_words, list):
        raise ValueError('list_words must be a list')

    if not len(list_words):
        return []

    if not isinstance(list_words[0], str):
        raise ValueError('list_words must be a list of strings')

    dict_words = {}
    for word in list_words:
        found = False
        for key in dict_words.keys():
            if word in key or any(
                [word in inside for inside in dict_words[key]]
            ):
                dict_words[key].append(word)
                found = True
            if key in word:
                dict_words[key].append(word)
        if not found:
            dict_words[word] = [word]
    results = []
    for key, words in dict_words.items():
        results.append(max(list(set([key] + words)), key = len))
    return list(set(results))


def cluster_pos(result):
    """
    cluster similar POS.

    Parameters
    ----------
    result: list

    Returns
    -------
    result: list
    """
    if not isinstance(result, list):
        raise ValueError('result must be a list')
    if not isinstance(result[0], tuple):
        raise ValueError('result must be a list of tuple')
    if not all([i[1] in _accepted_pos for i in result]):
        raise ValueError(
            'elements of result must be a subset or equal of supported POS, please run malaya.describe_pos() to get supported POS'
        )

    output = {
        'ADJ': [],
        'ADP': [],
        'ADV': [],
        'ADX': [],
        'AUX': [],
        'CCONJ': [],
        'DET': [],
        'NOUN': [],
        'NUM': [],
        'PART': [],
        'PRON': [],
        'PROPN': [],
        'SCONJ': [],
        'SYM': [],
        'VERB': [],
        'X': [],
    }
    last_label, words = None, []
    for word, label in result:
        if last_label != label and last_label:
            joined = ' '.join(words)
            if joined not in output[last_label]:
                output[last_label].append(joined)
            words = []
            last_label = label
            words.append(word)

        else:
            if not last_label:
                last_label = label
            words.append(word)
    output[last_label].append(' '.join(words))
    return output


def cluster_tagging(result):
    """
    cluster any tagging results, as long the data passed `[(string, label), (string, label)]`.

    Parameters
    ----------
    result: list

    Returns
    -------
    result: list
    """
    if not isinstance(result, list):
        raise ValueError('result must be a list')
    if not isinstance(result[0], tuple):
        raise ValueError('result must be a list of tuple')

    _, labels = list(zip(*result))

    output = {l: [] for l in labels}
    last_label, words = None, []
    for word, label in result:
        if last_label != label and last_label:
            joined = ' '.join(words)
            if joined not in output[last_label]:
                output[last_label].append(joined)
            words = []
            last_label = label
            words.append(word)

        else:
            if not last_label:
                last_label = label
            words.append(word)
    output[last_label].append(' '.join(words))
    return output


def cluster_entities(result):
    """
    cluster similar Entities.

    Parameters
    ----------
    result: list

    Returns
    -------
    result: list
    """
    if not isinstance(result, list):
        raise ValueError('result must be a list')
    if not isinstance(result[0], tuple):
        raise ValueError('result must be a list of tuple')
    if not all([i[1] in _accepted_entities for i in result]):
        raise ValueError(
            'elements of result must be a subset or equal of supported Entities, please run malaya.describe_entities() to get supported POS'
        )

    output = {
        'OTHER': [],
        'law': [],
        'location': [],
        'organization': [],
        'person': [],
        'quantity': [],
        'time': [],
        'event': [],
        'X': [],
    }
    last_label, words = None, []
    for word, label in result:
        if last_label != label and last_label:
            joined = ' '.join(words)
            if joined not in output[last_label]:
                output[last_label].append(joined)
            words = []
            last_label = label
            words.append(word)

        else:
            if not last_label:
                last_label = label
            words.append(word)
    output[last_label].append(' '.join(words))
    return output


def cluster_scatter(
    corpus,
    vectorizer,
    num_clusters = 5,
    titles = None,
    colors = None,
    stemming = True,
    stop_words = None,
    cleaning = simple_textcleaning,
    clustering = KMeans,
    decomposition = MDS,
    ngram = (1, 3),
    figsize = (17, 9),
    batch_size = 20,
):
    """
    plot scatter plot on similar text clusters.

    Parameters
    ----------

    corpus: list
    vectorizer: class
    num_clusters: int, (default=5)
        size of unsupervised clusters.
    titles: list
        list of titles, length must same with corpus.
    colors: list
        list of colors, length must same with num_clusters.
    stemming: bool, (default=True)
        If True, sastrawi_stemmer will apply.
    stop_words: list, (default=None)
        list of stop words to remove. If None, default is malaya.texts._text_functions.STOPWORDS
    ngram: tuple, (default=(1,3))
        n-grams size to train a corpus.
    cleaning: function, (default=simple_textcleaning)
        function to clean the corpus.
    batch_size: int, (default=10)
        size of strings for each vectorization and attention. Only useful if use transformer vectorizer.

    Returns
    -------
    dictionary: {'X': X, 'Y': Y, 'labels': clusters, 'vector': transformed_text_clean, 'titles': titles}
    """
    if not isinstance(corpus, list):
        raise ValueError('corpus must be a list')
    if not isinstance(corpus[0], str):
        raise ValueError('corpus must be list of strings')
    if not isinstance(titles, list) and titles is not None:
        raise ValueError('titles must be a list or None')
    if not isinstance(colors, list) and colors is not None:
        raise ValueError('colors must be a list or None')
    if not isinstance(batch_size, int):
        raise ValueError('batch_size must be an integer')
    if titles:
        if len(titles) != len(corpus):
            raise ValueError('length of titles must be same with corpus')
    if colors:
        if len(colors) != num_clusters:
            raise ValueError(
                'size of colors must be same with number of clusters'
            )
    if not hasattr(vectorizer, 'vectorize') and not hasattr(vectorizer, 'fit'):
        raise ValueError('vectorizer must has `fit` and `vectorize` methods')
    if not isinstance(stemming, bool):
        raise ValueError('bool must be a boolean')

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set()
    except:
        raise Exception(
            'matplotlib and seaborn not installed. Please install it and try again.'
        )

    if stop_words is None:
        stop_words = STOPWORDS

    if cleaning is not None:
        for i in range(len(corpus)):
            corpus[i] = cleaning(corpus[i])
    if stemming:
        for i in range(len(corpus)):
            corpus[i] = sastrawi(corpus[i])
    text_clean = []
    for text in corpus:
        text_clean.append(
            ' '.join([word for word in text.split() if word not in stop_words])
        )

    if hasattr(vectorizer, 'fit'):
        vectorizer.fit(text_clean)
        transformed_text_clean = vectorizer.transform(text_clean)
        features = vectorizer.get_feature_names()
    else:
        transformed_text_clean, attentions = [], []
        for i in range(0, len(text_clean), batch_size):
            index = min(i + batch_size, len(text_clean))
            transformed_text_clean.append(
                vectorizer.vectorize(text_clean[i:index])
            )
            attentions.extend(vectorizer.attention(text_clean[i:index]))
        transformed_text_clean = np.concatenate(
            transformed_text_clean, axis = 0
        )
    km = clustering(n_clusters = num_clusters)
    dist = 1 - cosine_similarity(transformed_text_clean)
    km.fit(transformed_text_clean)
    clusters = km.labels_.tolist()
    if isinstance(decomposition, MDS):
        decomposed = decomposition(
            n_components = 2, dissimilarity = 'precomputed'
        )
    else:
        decomposed = decomposition(n_components = 2)
    pos = decomposed.fit_transform(dist)
    if not titles:
        titles = []
        for i in range(transformed_text_clean.shape[0]):

            if hasattr(vectorizer, 'fit'):
                indices = np.argsort(
                    np.array(transformed_text_clean[i].todense())[0]
                )[::-1]
                titles.append(
                    ' '.join([features[i] for i in indices[: ngram[1]]])
                )
            else:
                attentions[i].sort(key = lambda x: x[1])
                titles.append(
                    ' '.join([i[0] for i in attentions[i][-ngram[1] :]])
                )

    if not colors:
        colors = sns.color_palette(n_colors = num_clusters)
    X, Y = pos[:, 0], pos[:, 1]
    plt.figure(figsize = figsize)
    for i in np.unique(clusters):
        plt.scatter(
            X[clusters == i],
            Y[clusters == i],
            color = colors[i],
            label = 'cluster %d' % (i),
        )
    for i in range(len(X)):
        plt.text(X[i], Y[i], titles[i], size = 8)
    plt.legend()
    plt.show()
    return {
        'X': X,
        'Y': Y,
        'labels': clusters,
        'vector': transformed_text_clean,
        'titles': titles,
    }


def cluster_dendogram(
    corpus,
    vectorizer,
    titles = None,
    stemming = True,
    stop_words = None,
    cleaning = simple_textcleaning,
    random_samples = 0.3,
    ngram = (1, 3),
    figsize = (17, 9),
    batch_size = 20,
    **kwargs
):
    """
    plot hierarchical dendogram with similar texts.

    Parameters
    ----------

    corpus: list
    vectorizer: class
    num_clusters: int, (default=5)
        size of unsupervised clusters.
    titles: list
        list of titles, length must same with corpus.
    stemming: bool, (default=True)
        If True, sastrawi_stemmer will apply.
    stop_words: list, (default=None)
        list of stop words to remove. If None, default is malaya.texts._text_functions.STOPWORDS
    cleaning: function, (default=simple_textcleaning)
        function to clean the corpus.
    random_samples: float, (default=0.3)
        random samples from the corpus, 0.3 means 30%.
    ngram: tuple, (default=(1,3))
        n-grams size to train a corpus.
    batch_size: int, (default=20)
        size of strings for each vectorization and attention. Only useful if use transformer vectorizer.

    Returns
    -------
    dictionary: {'linkage_matrix': linkage_matrix, 'titles': titles}
    """
    if not isinstance(corpus, list):
        raise ValueError('corpus must be a list')
    if not isinstance(corpus[0], str):
        raise ValueError('corpus must be list of strings')
    if not isinstance(titles, list) and titles is not None:
        raise ValueError('titles must be a list or None')
    if titles:
        if len(titles) != len(corpus):
            raise ValueError('length of titles must be same with corpus')
    if not isinstance(stemming, bool):
        raise ValueError('bool must be a boolean')

    if not hasattr(vectorizer, 'vectorize') and not hasattr(vectorizer, 'fit'):
        raise ValueError('vectorizer must has `fit` and `vectorize` methods')
    if not isinstance(random_samples, float):
        raise ValueError('random_samples must be a float')
    if not (random_samples < 1 and random_samples > 0):
        raise ValueError('random_samples must be between 0 and 1')
    if not isinstance(ngram, tuple):
        raise ValueError('ngram must be a tuple')
    if not len(ngram) == 2:
        raise ValueError('ngram size must equal to 2')

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        from scipy.cluster.hierarchy import ward, dendrogram

        sns.set()
    except:
        raise Exception(
            'matplotlib and seaborn not installed. Please install it and try again.'
        )
    if stop_words is None:
        stop_words = STOPWORDS

    corpus = random.sample(corpus, k = int(random_samples * len(corpus)))

    if cleaning is not None:
        for i in range(len(corpus)):
            corpus[i] = cleaning(corpus[i])
    if stemming:
        for i in range(len(corpus)):
            corpus[i] = sastrawi(corpus[i])
    text_clean = []
    for text in corpus:
        text_clean.append(
            ' '.join([word for word in text.split() if word not in stop_words])
        )

    if hasattr(vectorizer, 'fit'):
        vectorizer.fit(text_clean)
        transformed_text_clean = vectorizer.transform(text_clean)
        features = vectorizer.get_feature_names()
    else:
        transformed_text_clean, attentions = [], []
        for i in range(0, len(text_clean), batch_size):
            index = min(i + batch_size, len(text_clean))
            transformed_text_clean.append(
                vectorizer.vectorize(text_clean[i:index])
            )
            attentions.extend(vectorizer.attention(text_clean[i:index]))
        transformed_text_clean = np.concatenate(
            transformed_text_clean, axis = 0
        )

    dist = 1 - cosine_similarity(transformed_text_clean)
    linkage_matrix = ward(dist)
    if not titles:
        titles = []
        for i in range(transformed_text_clean.shape[0]):

            if hasattr(vectorizer, 'fit'):
                indices = np.argsort(
                    np.array(transformed_text_clean[i].todense())[0]
                )[::-1]
                titles.append(
                    ' '.join([features[i] for i in indices[: ngram[1]]])
                )
            else:
                attentions[i].sort(key = lambda x: x[1])
                titles.append(
                    ' '.join([i[0] for i in attentions[i][-ngram[1] :]])
                )
    plt.figure(figsize = figsize)
    ax = dendrogram(linkage_matrix, orientation = 'right', labels = titles)
    plt.tick_params(
        axis = 'x',
        which = 'both',
        bottom = 'off',
        top = 'off',
        labelbottom = 'off',
    )
    plt.tight_layout()
    plt.show()
    return {'linkage_matrix': linkage_matrix, 'titles': titles}


def cluster_graph(
    corpus,
    vectorizer,
    threshold = 0.9,
    num_clusters = 5,
    titles = None,
    colors = None,
    stop_words = None,
    stemming = True,
    ngram = (1, 3),
    cleaning = simple_textcleaning,
    clustering = KMeans,
    figsize = (17, 9),
    with_labels = True,
    batch_size = 20,
    **kwargs
):
    """
    plot undirected graph with similar texts.

    Parameters
    ----------

    corpus: list
    vectorizer: class
    threshold: float, (default=0.9)
        0.9 means, 90% above absolute pearson correlation.
    num_clusters: int, (default=5)
        size of unsupervised clusters.
    titles: list
        list of titles, length must same with corpus.
    stemming: bool, (default=True)
        If True, sastrawi_stemmer will apply.
    stop_words: list, (default=None)
        list of stop words to remove. If None, default is malaya.texts._text_functions.STOPWORDS
    cleaning: function, (default=simple_textcleaning)
        function to clean the corpus.
    ngram: tuple, (default=(1,3))
        n-grams size to train a corpus.
    batch_size: int, (default=20)
        size of strings for each vectorization and attention. Only useful if use transformer vectorizer.

    Returns
    -------
    dictionary: {'G': G, 'pos': pos, 'node_colors': node_colors, 'node_labels': node_labels}
    """

    if not isinstance(corpus, list):
        raise ValueError('corpus must be a list')
    if not isinstance(corpus[0], str):
        raise ValueError('corpus must be list of strings')
    if not isinstance(titles, list) and titles is not None:
        raise ValueError('titles must be a list or None')
    if not isinstance(colors, list) and colors is not None:
        raise ValueError('colors must be a list or None')
    if titles:
        if len(titles) != len(corpus):
            raise ValueError('length of titles must be same with corpus')
    if colors:
        if len(colors) != num_clusters:
            raise ValueError(
                'size of colors must be same with number of clusters'
            )
    if not hasattr(vectorizer, 'vectorize') and not hasattr(vectorizer, 'fit'):
        raise ValueError('vectorizer must has `fit` and `vectorize` methods')
    if not isinstance(stemming, bool):
        raise ValueError('bool must be a boolean')
    if not isinstance(ngram, tuple):
        raise ValueError('ngram must be a tuple')
    if not len(ngram) == 2:
        raise ValueError('ngram size must equal to 2')
    if not isinstance(threshold, float):
        raise ValueError('threshold must be a float')
    if not (threshold <= 1 and threshold > 0):
        raise ValueError(
            'threshold must be bigger than 0, less than or equal to 1'
        )

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import networkx as nx
        import networkx.drawing.layout as nxlayout
        import pandas as pd

        sns.set()
    except:
        raise Exception(
            'matplotlib, seaborn, networkx not installed. Please install it and try again.'
        )
    if stop_words is None:
        stop_words = STOPWORDS

    if cleaning is not None:
        for i in range(len(corpus)):
            corpus[i] = cleaning(corpus[i])
    if stemming:
        for i in range(len(corpus)):
            corpus[i] = sastrawi(corpus[i])
    text_clean = []
    for text in corpus:
        text_clean.append(
            ' '.join([word for word in text.split() if word not in stop_words])
        )

    if hasattr(vectorizer, 'fit'):
        vectorizer.fit(text_clean)
        transformed_text_clean = vectorizer.transform(text_clean).todense()
        features = vectorizer.get_feature_names()
    else:
        transformed_text_clean, attentions = [], []
        for i in range(0, len(text_clean), batch_size):
            index = min(i + batch_size, len(text_clean))
            transformed_text_clean.append(
                vectorizer.vectorize(text_clean[i:index])
            )
            attentions.extend(vectorizer.attention(text_clean[i:index]))
        transformed_text_clean = np.concatenate(
            transformed_text_clean, axis = 0
        )

    DxT = transformed_text_clean
    DxD = np.abs(pd.DataFrame(DxT.T).corr()).values
    km = clustering(n_clusters = num_clusters)
    km.fit(DxT)
    clusters = km.labels_.tolist()

    if not titles:
        titles = []
        for i in range(transformed_text_clean.shape[0]):

            if hasattr(vectorizer, 'fit'):
                indices = np.argsort(np.array(transformed_text_clean[i])[0])[
                    ::-1
                ]
                titles.append(
                    ' '.join([features[i] for i in indices[: ngram[1]]])
                )
            else:
                attentions[i].sort(key = lambda x: x[1])
                titles.append(
                    ' '.join([i[0] for i in attentions[i][-ngram[1] :]])
                )

    if not colors:
        colors = sns.color_palette(n_colors = num_clusters)
    G = nx.Graph()
    for i in range(DxT.shape[0]):
        G.add_node(i, text = titles[i], label = clusters[i])

    len_dense = len(DxD)
    for i in range(len_dense):
        for j in range(len_dense):
            if j == i:
                continue
            if DxD[i, j] >= threshold:
                weight = DxD[i, j]
                G.add_edge(i, j, weight = weight)
    node_colors, node_labels = [], {}
    for node in G:
        node_colors.append(colors[G.node[node]['label']])
        node_labels[node] = G.node[node]['text']
    pos = nxlayout.fruchterman_reingold_layout(
        G, k = 1.5 / np.sqrt(len(G.nodes()))
    )
    plt.figure(figsize = figsize)
    if with_labels:
        nx.draw(G, node_color = node_colors, pos = pos, labels = node_labels)
    else:
        nx.draw(G, node_color = node_colors, pos = pos)

    return {
        'G': G,
        'pos': pos,
        'node_colors': node_colors,
        'node_labels': node_labels,
    }


def cluster_entity_linking(
    corpus,
    vectorizer,
    entity_model,
    topic_modeling_model,
    threshold = 0.3,
    topic_decomposition = 2,
    topic_length = 10,
    fuzzy_ratio = 70,
    accepted_entities = ['law', 'location', 'organization', 'person', 'event'],
    cleaning = simple_textcleaning,
    stemming = True,
    colors = None,
    stop_words = None,
    max_df = 1.0,
    min_df = 1,
    ngram = (2, 3),
    figsize = (17, 9),
    batch_size = 20,
    **kwargs
):
    """
    plot undirected graph for Entities and topics relationship.

    Parameters
    ----------
    corpus: list or str
    vectorizer: class
    titles: list
        list of titles, length must same with corpus.
    colors: list
        list of colors, length must same with num_clusters.
    threshold: float, (default=0.3)
        0.3 means, 30% above absolute pearson correlation.
    topic_decomposition: int, (default=2)
        size of decomposition.
    topic_length: int, (default=10)
        size of topic models.
    fuzzy_ratio: int, (default=70)
        size of ratio for fuzzywuzzy.
    stemming: bool, (default=True)
        If True, sastrawi_stemmer will apply.
    max_df: float, (default=0.95)
        maximum of a word selected based on document frequency.
    min_df: int, (default=2)
        minimum of a word selected on based on document frequency.
    ngram: tuple, (default=(1,3))
        n-grams size to train a corpus.
    cleaning: function, (default=simple_textcleaning)
        function to clean the corpus.
    stop_words: list, (default=None)
        list of stop words to remove. If None, default is malaya.texts._text_functions.STOPWORDS

    Returns
    -------
    dictionary: {'G': G, 'pos': pos, 'node_colors': node_colors, 'node_labels': node_labels}
    """

    import inspect

    if not isinstance(corpus, list) and not isinstance(corpus, str):
        raise ValueError('corpus must be a list')
    if isinstance(corpus, list):
        if not isinstance(corpus[0], str):
            raise ValueError('corpus must be list of strings')
    if not hasattr(vectorizer, 'vectorize') and not hasattr(vectorizer, 'fit'):
        raise ValueError('vectorizer must has `fit` and `vectorize` methods')
    if 'max_df' not in inspect.getargspec(topic_modeling_model)[0]:
        raise ValueError('topic_modeling_model must has `max_df` parameter')
    if not isinstance(colors, list) and colors is not None:
        raise ValueError('colors must be a list or None')
    if not isinstance(stemming, bool):
        raise ValueError('bool must be a boolean')
    if not isinstance(ngram, tuple):
        raise ValueError('ngram must be a tuple')
    if not len(ngram) == 2:
        raise ValueError('ngram size must equal to 2')
    if not isinstance(min_df, int):
        raise ValueError('min_df must be an integer')
    if not isinstance(topic_decomposition, int):
        raise ValueError('topic_decomposition must be an integer')
    if not isinstance(topic_length, int):
        raise ValueError('topic_length must be an integer')
    if not isinstance(fuzzy_ratio, int):
        raise ValueError('fuzzy_ratio must be an integer')
    if not isinstance(max_df, float):
        raise ValueError('max_df must be a float')

    if min_df < 1:
        raise ValueError('min_df must be bigger than 0')
    if not (max_df <= 1 and max_df > 0):
        raise ValueError(
            'max_df must be bigger than 0, less than or equal to 1'
        )
    if not (fuzzy_ratio > 0 and fuzzy_ratio <= 100):
        raise ValueError(
            'fuzzy_ratio must be bigger than 0, less than or equal to 100'
        )
    if not isinstance(threshold, float):
        raise ValueError('threshold must be a float')
    if not (threshold <= 1 and threshold > 0):
        raise ValueError(
            'threshold must be bigger than 0, less than or equal to 1'
        )
    if stop_words is None:
        stop_words = STOPWORDS

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import networkx as nx
        import networkx.drawing.layout as nxlayout
        import pandas as pd
        from fuzzywuzzy import fuzz

        sns.set()
    except:
        raise Exception(
            'matplotlib, seaborn, networkx, fuzzywuzzy not installed. Please install it and try again.'
        )

    if isinstance(corpus, str):
        corpus = split_into_sentences(corpus)
    else:
        corpus = '. '.join(corpus)
        corpus = split_into_sentences(corpus)

    corpus = [string for string in corpus if len(string) > 5]

    if not colors:
        colors = sns.color_palette(n_colors = len(accepted_entities) + 1)
    else:
        if len(colors) != (len(accepted_entities) + 1):
            raise ValueError(
                'len of colors must same as %d' % (len(accepted_entities) + 1)
            )

    topic_model = topic_modeling_model(
        corpus,
        topic_decomposition,
        ngram = ngram,
        max_df = max_df,
        min_df = min_df,
    )
    topics = []
    for no, topic in enumerate(topic_model.comp.components_):
        for i in topic.argsort()[: -topic_length - 1 : -1]:
            topics.append(topic_model.features[i])

    entities_cluster = {entity: [] for entity in accepted_entities}
    for string in corpus:
        entities_clustered = cluster_entities(entity_model.predict(string))
        for entity in accepted_entities:
            entities_cluster[entity].extend(entities_clustered[entity])
    for entity in accepted_entities:
        entities_cluster[entity] = cluster_words(
            list(set(entities_cluster[entity]))
        )

    topics = cluster_words(list(set(topics)))
    color_dict = {topic: colors[-1] for topic in topics}
    for no, entity in enumerate(accepted_entities):
        for e in entities_cluster[entity]:
            topics.append(e)
            color_dict[e] = colors[no]

    topics_corpus = []
    for topic in topics:
        nested_corpus = []
        for string in corpus:
            if (
                topic in string
                or fuzz.token_set_ratio(topic, string) >= fuzzy_ratio
            ):
                nested_corpus.append(string)
        topics_corpus.append(' '.join(nested_corpus))

    corpus = topics_corpus

    if cleaning is not None:
        for i in range(len(corpus)):
            corpus[i] = cleaning(corpus[i])
    if stemming:
        for i in range(len(corpus)):
            corpus[i] = sastrawi(corpus[i])
    text_clean = []
    for text in corpus:
        text_clean.append(
            ' '.join([word for word in text.split() if word not in stop_words])
        )

    if hasattr(vectorizer, 'fit'):
        vectorizer.fit(text_clean)
        transformed_text_clean = vectorizer.transform(text_clean).todense()
        features = vectorizer.get_feature_names()
    else:
        transformed_text_clean, attentions = [], []
        for i in range(0, len(text_clean), batch_size):
            index = min(i + batch_size, len(text_clean))
            transformed_text_clean.append(
                vectorizer.vectorize(text_clean[i:index])
            )
            attentions.extend(vectorizer.attention(text_clean[i:index]))
        transformed_text_clean = np.concatenate(
            transformed_text_clean, axis = 0
        )

    DxT = transformed_text_clean
    DxD = np.abs(pd.DataFrame(DxT.T).corr()).values

    G = nx.Graph()
    for i in range(DxT.shape[0]):
        G.add_node(i, text = topics[i], label = topics[i])

    len_dense = len(DxD)
    for i in range(len_dense):
        for j in range(len_dense):
            if j == i:
                continue
            if DxD[i, j] >= threshold:
                weight = DxD[i, j]
                G.add_edge(i, j, weight = weight)

    node_colors, node_labels = [], {}
    for node in G:
        node_colors.append(color_dict[G.node[node]['label']])
        node_labels[node] = G.node[node]['text']
    pos = nxlayout.fruchterman_reingold_layout(
        G, k = 1.5 / np.sqrt(len(G.nodes()))
    )
    f = plt.figure(figsize = figsize)
    ax = f.add_subplot(1, 1, 1)
    for no, entity in enumerate(accepted_entities):
        ax.plot([0], [0], color = colors[no], label = entity)
    ax.plot([0], [0], color = colors[-1], label = 'topics')
    nx.draw(
        G, node_color = node_colors, pos = pos, labels = node_labels, ax = ax
    )
    plt.legend()
    plt.tight_layout()
    plt.show()
    return {
        'G': G,
        'pos': pos,
        'node_colors': node_colors,
        'node_labels': node_labels,
    }
