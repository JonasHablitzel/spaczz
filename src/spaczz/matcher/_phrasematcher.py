"""Module for _PhraseMatcher with an API semi-analogous to spaCy matchers."""
from __future__ import annotations

from collections import defaultdict
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)
import warnings

from spacy.tokens import Doc
from spacy.vocab import Vocab

from ..exceptions import KwargsWarning
from ..search import _PhraseSearcher


class _PhraseMatcher:
    """spaCy-like matcher for finding flexible matches in `Doc` objects.

    Matches added patterns against the `Doc` object it is called on.
    Accepts labeled patterns in the form of `Doc` objects.

    Attributes:
        defaults: Keyword arguments to be used as default matching settings.
            See `_PhraseSearcher` documentation for details.
        name: Class attribute - the name of the matcher.
        type: The kind of matcher object.
        _callbacks:
            On match functions to modify `Doc` objects passed to the matcher.
            Can make use of the matches identified.
        _patterns:
            Patterns added to the matcher. Contains patterns
            and kwargs that should be used during matching
            for each labels added.
    """

    name = "_phrase_matcher"

    def __init__(self, vocab: Vocab, **defaults: Any) -> None:
        """Initializes the base phrase matcher with the given defaults.

        Args:
            vocab: A spacy `Vocab` object.
                Purely for consistency between spaCy
                and spaczz matcher APIs for now.
                spaczz matchers are currently pure
                Python and do not share vocabulary
                with spaCy pipelines.
            **defaults: Keyword arguments that will
                be used as default matching settings.
                These arguments will become the new defaults for matching.
                See `_PhraseSearcher` documentation for details.
        """
        self.defaults = defaults
        self.type = "_phrase"
        self._callbacks: Dict[
            str,
            Union[
                Callable[
                    [_PhraseMatcher, Doc, int, List[Tuple[str, int, int, int]]], None
                ],
                None,
            ],
        ] = {}
        self._patterns: DefaultDict[str, DefaultDict[str, Any]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._searcher = _PhraseSearcher(vocab=vocab)

    def __call__(self, doc: Doc) -> List[Tuple[str, int, int, int]]:
        """Find all sequences matching the supplied patterns in the doc.

        Args:
            doc: The `Doc` object to match over.

        Returns:
            A list of (key, start, end, ratio) tuples, describing the matches.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> doc = nlp("Ridley Scott was the director of Alien.")
            >>> matcher.add("NAME", [nlp("Ridley Scott")])
            >>> matcher(doc)
            [('NAME', 0, 2, 100)]
        """
        matches = set()
        for label, patterns in self._patterns.items():
            for pattern, kwargs in zip(patterns["patterns"], patterns["kwargs"]):
                if not kwargs:
                    kwargs = self.defaults
                matches_wo_label = self._searcher.match(doc, pattern, **kwargs)
                if matches_wo_label:
                    matches_w_label = [
                        (label,) + match_wo_label for match_wo_label in matches_wo_label
                    ]
                    for match in matches_w_label:
                        matches.add(match)
        if matches:
            sorted_matches = sorted(matches, key=lambda x: (x[1], -x[2] - x[1]))
            for i, (label, _start, _end, _ratio) in enumerate(sorted_matches):
                on_match = self._callbacks.get(label)
                if on_match:
                    on_match(self, doc, i, sorted_matches)
            return sorted_matches
        else:
            return []

    def __contains__(self, label: str) -> bool:
        """Whether the matcher contains patterns for a label."""
        return label in self._patterns

    def __len__(self) -> int:
        """The number of labels added to the matcher."""
        return len(self._patterns)

    @property
    def labels(self) -> Tuple[str, ...]:
        """All labels present in the matcher.

        Returns:
            The unique string labels as a tuple.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> matcher.add("AUTHOR", [nlp("Kerouac")])
            >>> matcher.labels
            ('AUTHOR',)
        """
        return tuple(self._patterns.keys())

    @property
    def patterns(self) -> List[Dict[str, Any]]:
        """Get all patterns and kwargs that were added to the matcher.

        Returns:
            The original patterns and kwargs,
            one dictionary for each combination.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> matcher.add("AUTHOR", [nlp("Kerouac")],
                [{"ignore_case": False}])
            >>> matcher.patterns == [
                {
                    "label": "AUTHOR",
                    "pattern": "Kerouac",
                    "type": "_phrase",
                    "kwargs": {"ignore_case": False}
                    },
                    ]
            True
        """
        all_patterns = []
        for label, patterns in self._patterns.items():
            for pattern, kwargs in zip(patterns["patterns"], patterns["kwargs"]):
                p = {"label": label, "pattern": pattern.text, "type": self.type}
                if kwargs:
                    p["kwargs"] = kwargs
                all_patterns.append(p)
        return all_patterns

    @property
    def vocab(self) -> Vocab:
        """Returns the spaCy `Vocab` object utilized."""
        return self._searcher.vocab

    def add(
        self,
        label: str,
        patterns: Sequence[Doc],
        kwargs: Optional[List[Dict[str, Any]]] = None,
        on_match: Optional[
            Callable[[_PhraseMatcher, Doc, int, List[Tuple[str, int, int, int]]], None]
        ] = None,
    ) -> None:
        """Add a rule to the matcher, consisting of a label and one or more patterns.

        Patterns must be a list of `Doc` object and if kwargs is not None,
        kwargs must be a list of dictionaries.

        Args:
            label: Name of the rule added to the matcher.
            patterns: `Doc` objects that will be matched
                against the `Doc` object the matcher is called on.
            kwargs: Optional arguments to modify the behavior of the matching.
                Apply to inherited multi_match method.
                See `_PhraseSearcher` documentation for kwarg details.
                Default is `None`.
            on_match: Optional callback function to modify the
                `Doc` object the matcher is called on after matching.
                Default is `None`.

        Raises:
            TypeError: If patterns is not an iterable of `Doc` objects.
            TypeError: If kwargs is not an iterable dictionaries.

        Warnings:
            UserWarning:
                If there are more patterns than kwargs
                default matching settings will be used
                for extra patterns.
            UserWarning:
                If there are more kwargs dicts than patterns,
                the extra kwargs will be ignored.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> matcher.add("SOUND", [nlp("mooo")])
            >>> "SOUND" in matcher
            True
        """
        if kwargs is None:
            kwargs = [{} for _ in patterns]
        elif len(kwargs) < len(patterns):
            warnings.warn(
                """There are more patterns then there are kwargs.\n
                Patterns not matched to a kwarg dict will have default settings.""",
                KwargsWarning,
            )
            kwargs.extend([{} for _ in range(len(patterns) - len(kwargs))])
        elif len(kwargs) > len(patterns):
            warnings.warn(
                """There are more kwargs dicts than patterns.\n
                The extra kwargs will be ignored.""",
                KwargsWarning,
            )
        for pattern, kwarg in zip(patterns, kwargs):
            if isinstance(pattern, Doc):
                self._patterns[label]["patterns"].append(pattern)
            else:
                raise TypeError("Patterns must be an iterable of Doc objects.")
            if isinstance(kwarg, dict):
                self._patterns[label]["kwargs"].append(kwarg)
            else:
                raise TypeError("Kwargs must be an iterable of dictionaries.")
        self._callbacks[label] = on_match

    def remove(self, label: str) -> None:
        """Remove a label and its respective patterns from the matcher.

        Args:
            label: Name of the rule added to the matcher.

        Raises:
            ValueError: If label does not exist in the matcher.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> matcher.add("SOUND", [nlp("mooo")])
            >>> matcher.remove("SOUND")
            >>> "SOUND" in matcher
            False
        """
        try:
            del self._patterns[label]
            del self._callbacks[label]
        except KeyError:
            raise ValueError(
                f"The label: {label} does not exist within the matcher rules."
            )

    def pipe(
        self,
        stream: Iterable[Doc],
        batch_size: int = 1000,
        return_matches: bool = False,
        as_tuples: bool = False,
    ) -> Generator[Any, None, None]:
        """Match a stream of `Doc` objects, yielding them in turn.

        Args:
            stream: A stream of `Doc` objects.
            batch_size: Number of documents to accumulate into a working set.
                Default is `1000`.
            return_matches: Yield the match lists along with the docs,
                making results (doc, matches) tuples. Default is `False`.
            as_tuples: Interpret the input stream as (doc, context) tuples,
                and yield (result, context) tuples out.
                If both return_matches and as_tuples are `True`,
                the output will be a sequence of ((doc, matches), context) tuples.
                Default is `False`.

        Yields:
            `Doc` objects, in order.

        Example:
            >>> import spacy
            >>> from spaczz.matcher import _PhraseMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = _PhraseMatcher(nlp.vocab)
            >>> doc_stream = (
                    nlp("test doc1: Korvold"),
                    nlp("test doc2: Prossh"),
                )
            >>> matcher.add("DRAGON", [nlp("Korvold"), nlp("Prossh")])
            >>> output = matcher.pipe(doc_stream, return_matches=True)
            >>> [entry[1] for entry in output]
            [[('DRAGON', 3, 4, 100)], [('DRAGON', 3, 4, 100)]]
        """
        if as_tuples:
            for doc, context in stream:
                matches = self(doc)
                if return_matches:
                    yield ((doc, matches), context)
                else:
                    yield (doc, context)
        else:
            for doc in stream:
                matches = self(doc)
                if return_matches:
                    yield (doc, matches)
                else:
                    yield doc
