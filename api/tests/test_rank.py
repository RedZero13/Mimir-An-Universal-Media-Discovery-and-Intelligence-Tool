from mde import taxonomy
from mde.catalogue.repository import Relation, TermEvidence, WorkProfile
from mde.discovery.explain import explain
from mde.discovery.intent import Avoidance, Intent, LengthLimit, Preference
from mde.discovery.rank import rank


def work(slug, medium="film", terms=None, runtime=None, tier=2, assessed=True, creators=None, **kw):
    return WorkProfile(
        id=slug, slug=slug, medium=medium, title=slug.title(), original_title=None, year=kw.get("year", 2000),
        language=kw.get("language", "en"), countries=[], summary=None, runtime_minutes=runtime,
        playtime_hours=kw.get("playtime"), length_is_estimate=False, popularity_tier=tier,
        advisories_assessed=assessed, creators=creators or [],
        terms={k: TermEvidence(v, 0.7, "ai_assisted", "unreviewed", not k.startswith("genre:"))
               for k, v in (terms or {}).items()},
    )


def slugs(result):
    return [s.work.slug for s in result.results]


def test_stronger_match_ranks_higher_and_non_matches_are_dropped():
    works = [work("weak", terms={"mood:eerie": 0.4}), work("strong", terms={"mood:eerie": 1.0}),
             work("none", terms={"mood:comforting": 1.0})]
    r = rank(Intent("q", preferences=[Preference("mood:eerie", 1.0, "eerie")]), works)
    assert slugs(r) == ["strong", "weak"]
    assert r.weak_dropped == 1


def test_hard_advisory_excludes_but_unassessed_work_is_kept_with_caveat():
    works = [work("violent", terms={"mood:tense": 1, "advisory:graphic-violence": 0.8}),
             work("mild", terms={"mood:tense": 1, "advisory:graphic-violence": 0.1}),
             work("unknown", terms={"mood:tense": 1}, assessed=False)]
    intent = Intent("q", preferences=[Preference("mood:tense", 1, "tense")],
                    avoid=[Avoidance("advisory:graphic-violence", True, 0.4, "violence")])
    r = rank(intent, works)
    assert slugs(r) == ["mild", "unknown"]
    assert r.excluded["content you asked to avoid"] == 1
    assert r.results[1].caveats == ["Not yet assessed for graphic violence."]
    assert r.results[0].caveats == []


def test_soft_length_penalises_and_explains_but_hard_length_excludes():
    works = [work("long", terms={"mood:eerie": 1}, runtime=170), work("short", terms={"mood:eerie": 1}, runtime=95)]
    pref = [Preference("mood:eerie", 1, "eerie")]
    soft = rank(Intent("q", preferences=pref, length=LengthLimit(120, False, "ideally under two hours")), works)
    assert slugs(soft) == ["short", "long"]
    assert any("50 min over" in c for c in soft.results[1].caveats)
    hard = rank(Intent("q", preferences=pref, length=LengthLimit(120, True, "under two hours")), works)
    assert slugs(hard) == ["short"]


def test_unknown_length_is_not_silently_treated_as_fitting():
    r = rank(Intent("q", preferences=[Preference("mood:eerie", 1, "")], length=LengthLimit(120, True, "")),
             [work("unknown", terms={"mood:eerie": 1})])
    assert slugs(r) == ["unknown"]
    assert any("isn't recorded" in c for c in r.results[0].caveats)


def test_obscure_preference_lifts_lesser_known_works():
    works = [work("famous", terms={"mood:eerie": 1}, tier=1), work("obscure", terms={"mood:eerie": 1}, tier=4)]
    r = rank(Intent("q", preferences=[Preference("mood:eerie", 1, "")], novelty="obscure"), works)
    assert slugs(r) == ["obscure", "famous"]


def test_reference_similarity_ignores_genre_across_media_and_uses_relationships():
    ref = work("ref", medium="game", terms={"genre:rpg": 1, "theme:politics-society": 1, "mood:melancholic": 0.8})
    book = work("book", medium="book", terms={"theme:politics-society": 0.9, "mood:melancholic": 0.8})
    adapted = work("adapted", medium="book", terms={"mood:melancholic": 0.5})
    adapted.relations.append(Relation("ref", "Ref", "game", "adaptation_of", "is an adaptation of", None, 0.9,
                                      "editorial", True))
    r = rank(Intent("q", reference_slug="ref", reference_other_medium=True), [ref, book, adapted])
    assert set(slugs(r)) == {"book", "adapted"}
    by = {s.work.slug: s for s in r.results}
    # (0.9 + 0.8 * 0.9) / (1 + 0.8 * 0.9), with mood weighted 0.9: the game's 'rpg' genre is left out for a book.
    assert by["book"].breakdown["reference_similarity"] == 0.942
    assert by["adapted"].relation is not None


def test_diversity_spreads_creators():
    works = [work("a1", terms={"mood:eerie": 1}, creators=["A"]), work("a2", terms={"mood:eerie": 0.99}, creators=["A"]),
             work("b1", terms={"mood:eerie": 0.95}, creators=["B"])]
    r = rank(Intent("q", preferences=[Preference("mood:eerie", 1, "")]), works)
    assert slugs(r) == ["a1", "b1", "a2"]


def test_explanations_are_grounded_in_evidence():
    w = work("w", terms={"mood:eerie": 0.9, "genre:horror": 1.0}, runtime=100)
    r = rank(Intent("q", preferences=[Preference("mood:eerie", 1, ""), Preference("genre:horror", 1.2, ""),
                                      Preference("theme:memory", 1, "")],
                    length=LengthLimit(120, False, "")), [w])
    e = explain(r.results[0], taxonomy.load())
    matches = [x for x in e["reasons"] if x["kind"] == "match"]
    assert {m["term"] for m in matches} == {"mood:eerie", "genre:horror"}
    assert {m["basis"] for m in matches} == {"interpretation", "catalogue"}
    assert any("fits your 120-minute limit" in x["text"] for x in e["reasons"])
    assert any("memory" in c for c in e["caveats"])     # requested but absent → said so, not hidden
