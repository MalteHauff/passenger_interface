import numpy

from passenger_interface.speech_to_text_utils import (
    calculate_blocksize,
    calculate_rms,
    is_meaningful_transcript,
    UtteranceBuffer,
)


def test_blocksize_uses_input_sample_rate():
    assert calculate_blocksize(sample_rate=48000, duration=0.1) == 4800


def test_calculate_rms_for_silence():
    assert calculate_rms(numpy.zeros(100, dtype=numpy.float32)) == 0.0


def test_calculate_rms_for_constant_signal():
    audio = numpy.full(100, 0.25, dtype=numpy.float32)

    assert calculate_rms(audio) == 0.25


def test_calculate_rms_for_empty_buffer():
    assert calculate_rms(numpy.array([], dtype=numpy.float32)) == 0.0


def test_meaningful_transcript_rejects_empty_and_punctuation():
    assert not is_meaningful_transcript("")
    assert not is_meaningful_transcript(". . . .")
    assert not is_meaningful_transcript("?! …")


def test_meaningful_transcript_accepts_words_and_numbers():
    assert is_meaningful_transcript("slow down")
    assert is_meaningful_transcript("take exit 3")


def test_utterance_buffer_joins_speech_until_end_silence():
    buffer = UtteranceBuffer(
        sample_rate=100,
        chunk_duration=0.1,
        pre_roll_duration=0.2,
        end_silence_duration=0.2,
        max_utterance_duration=2.0,
    )
    silence = numpy.zeros(10, dtype=numpy.float32)
    speech = numpy.ones(10, dtype=numpy.float32)

    assert buffer.add(silence, contains_speech=False) == (None, False)
    assert buffer.add(silence, contains_speech=False) == (None, False)
    assert buffer.add(speech, contains_speech=True) == (None, True)
    assert buffer.add(speech, contains_speech=True) == (None, False)
    assert buffer.add(silence, contains_speech=False) == (None, False)

    completed, started = buffer.add(silence, contains_speech=False)

    assert not started
    assert completed.size == 60
    assert numpy.count_nonzero(completed) == 20


def test_utterance_buffer_enforces_maximum_duration():
    buffer = UtteranceBuffer(
        sample_rate=100,
        chunk_duration=0.1,
        pre_roll_duration=0.0,
        end_silence_duration=0.5,
        max_utterance_duration=0.3,
    )
    speech = numpy.ones(10, dtype=numpy.float32)

    assert buffer.add(speech, contains_speech=True) == (None, True)
    assert buffer.add(speech, contains_speech=True) == (None, False)

    completed, started = buffer.add(speech, contains_speech=True)

    assert not started
    assert completed.size == 30
