# Last updated: 2026-08-04 09:56:45
# @nova-adjacent: voice_gateway — committer unit tests. Pure python, no deps. Run:
#   python general_tools/voice_gateway/test_committer.py
"""Tests for the sentence-committer — the one piece with real logic, so the one with tests."""
from committer import SentenceCommitter, commit_block


def _texts(units):
    return [u.text for u in units]


def test_basic_sentences():
    got = _texts(commit_block("Hey Cole. The build is green. Ship it?"))
    assert got == ["Hey Cole.", "The build is green.", "Ship it?"], got


def test_decimal_not_a_boundary():
    got = _texts(commit_block("The model runs at 22.4 tokens per second reliably."))
    assert got == ["The model runs at 22.4 tokens per second reliably."], got


def test_abbreviation_not_a_boundary():
    got = _texts(commit_block("Ask Dr. Smith about the e.g. case first, then report."))
    assert got == ["Ask Dr. Smith about the e.g. case first, then report."], got


def test_tiny_fragment_merges_forward():
    # "Yeah." is under min_chars → merges into the next sentence, not its own choppy utterance.
    got = _texts(commit_block("Yeah. I already checked the receipt and it holds."))
    assert got == ["Yeah. I already checked the receipt and it holds."], got


def test_streaming_emits_as_it_goes():
    c = SentenceCommitter()
    out = []
    for tok in ["The witness ", "objected. ", "I checked ", "the file ", "and I was right. ", "Done"]:
        out += c.feed(tok)
    # two complete sentences should have emitted mid-stream, before flush
    assert _texts(out) == ["The witness objected.", "I checked the file and I was right."], _texts(out)
    rest = _texts(c.flush())
    assert rest == ["Done"], rest


def test_long_sentence_soft_flushes_for_first_audio():
    long = ("So the thing about the witness is that it holds less context than she does on "
            "purpose, which is exactly what keeps it clean of her frame, and that is the whole "
            "point of the design we shipped tonight and tested twice")
    c = SentenceCommitter(max_buffer=120)
    units = c.feed(long) + c.flush()
    assert len(units) >= 2, "a very long sentence should soft-flush at a clause boundary"
    assert any(u.soft for u in units), "at least one soft (clause) boundary flush expected"
    # nothing is lost: rejoining reconstructs the text (modulo whitespace)
    joined = " ".join(u.text for u in units)
    assert joined.replace("  ", " ").split() == long.split(), joined


def test_claim_gate_tags_units():
    gate = lambda t: any(ch.isdigit() for ch in t)
    units = commit_block("I feel good about it. The file is 566 bytes.", claim_gate=gate)
    assert units[0].is_claim is False
    assert units[1].is_claim is True


def test_nothing_lost_on_final():
    got = _texts(commit_block("No terminator here"))
    assert got == ["No terminator here"], got


def test_empty():
    assert commit_block("") == []
    assert commit_block("   ") == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  ok  {fn.__name__}")
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERR   {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    raise SystemExit(0 if passed == len(fns) else 1)
