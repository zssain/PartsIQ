from app.lexical import LexicalScorer, PartDocument, query_terms

DOCUMENTS = [
    PartDocument(1, ("Oil filter", "فلتر زيت"), ("lube filter", "فلتر الزيت"), "filters Spin-on"),
    PartDocument(2, ("Fuel filter", "فلتر وقود"), ("diesel filter", "فلتر ديزل"), "filters Spin-on"),
    PartDocument(3, ("Air filter element", "فلتر هواء"), ("air cleaner",), "filters element"),
    PartDocument(4, ("Starter motor", "سلف"), ("starter", "self starter"), "electrical 24 V"),
    PartDocument(5, ("Water pump", "طرمبة ماء"), ("coolant pump", "طرمبة موية"), "cooling"),
    PartDocument(6, ("Fuel water separator", "فاصل الماء عن الوقود"), ("primary fuel filter",), "filters"),
    PartDocument(7, ("Air oil separator element", "فاصل الزيت والهواء"), ("فاصل زيت", "فلتر السبريتر"), "filters"),
]


def _top(query: str) -> int:
    return LexicalScorer().score(query, DOCUMENTS)[0].part_id


def test_discriminating_word_outweighs_shared_word() -> None:
    assert _top("I need the fuel filter please") == 2
    assert _top("oil filter") == 1


def test_arabic_and_colloquial_queries() -> None:
    assert _top("ابغى فلتر ديزل") == 2
    assert _top("الطرمبة خربانة") == 5
    assert _top("السلف") == 4


def test_misspelling_is_tolerated() -> None:
    assert _top("startr motr") == 4


def test_scores_are_bounded_and_exact_name_scores_one() -> None:
    results = LexicalScorer().score("fuel filter", DOCUMENTS)
    assert all(0.0 <= r.score <= 1.0 for r in results)
    assert results[0].part_id == 2 and results[0].score == 1.0


def test_name_phrase_outranks_alias_phrase_and_scattered_words() -> None:
    fuel = LexicalScorer().score("fuel filter", DOCUMENTS)
    assert fuel[0].part_id == 2 and fuel[1].part_id == 6 and fuel[0].score > fuel[1].score
    oil = LexicalScorer().score("فلتر زيت", DOCUMENTS)
    assert oil[0].part_id == 1 and oil[0].score > oil[1].score


def test_machine_terms_are_ignored() -> None:
    with_model = LexicalScorer().score("VP-100 fuel filter", DOCUMENTS, frozenset({"vp", "vp100"}))
    assert with_model[0].part_id == 2 and with_model[0].score == 1.0


def test_query_with_no_informative_terms_scores_zero() -> None:
    assert all(r.score == 0 for r in LexicalScorer().score("please send price", DOCUMENTS))


def test_query_terms_drop_stopwords_and_numbers() -> None:
    assert query_terms("Please I need 2 oil filters") == ["oil", "filters"]
