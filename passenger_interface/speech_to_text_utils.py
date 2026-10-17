import re
from collections import deque

import numpy


class UtteranceBuffer:
    """Collect short audio chunks until an utterance-ending silence."""

    def __init__(
        self,
        sample_rate: int,
        chunk_duration: float,
        pre_roll_duration: float,
        end_silence_duration: float,
        max_utterance_duration: float,
    ):
        pre_roll_chunks = max(
            0,
            round(pre_roll_duration / chunk_duration),
        )
        self._pre_roll_chunks = pre_roll_chunks
        self._pre_roll = deque(maxlen=pre_roll_chunks)
        self._end_silence_samples = int(
            sample_rate * end_silence_duration
        )
        self._max_utterance_samples = int(
            sample_rate * max_utterance_duration
        )
        self._utterance = []
        self._utterance_samples = 0
        self._silence_samples = 0
        self._recording = False

    def add(
        self,
        audio: numpy.ndarray,
        contains_speech: bool,
    ) -> tuple[numpy.ndarray | None, bool]:
        """Add a chunk and return completed audio plus speech-start state."""
        speech_started = False

        if not self._recording:
            if not contains_speech:
                self._pre_roll.append(audio)
                return None, speech_started

            self._recording = True
            speech_started = True
            self._utterance = list(self._pre_roll)
            self._utterance_samples = sum(
                chunk.size for chunk in self._utterance
            )
            self._pre_roll.clear()

        self._utterance.append(audio)
        self._utterance_samples += audio.size

        if contains_speech:
            self._silence_samples = 0
        else:
            self._silence_samples += audio.size

        ended_by_silence = (
            self._silence_samples >= self._end_silence_samples
        )
        reached_maximum = (
            self._utterance_samples >= self._max_utterance_samples
        )
        if not ended_by_silence and not reached_maximum:
            return None, speech_started

        completed_audio = numpy.concatenate(self._utterance)

        if ended_by_silence and self._pre_roll_chunks:
            self._pre_roll.extend(
                self._utterance[-self._pre_roll_chunks:]
            )

        self._utterance = []
        self._utterance_samples = 0
        self._silence_samples = 0
        self._recording = False

        return completed_audio, speech_started


def calculate_blocksize(sample_rate: int, duration: float) -> int:
    """Return the number of input frames needed for an audio duration."""
    return int(sample_rate * duration)


def calculate_rms(audio: numpy.ndarray) -> float:
    """Return the root-mean-square level of an audio buffer."""
    if audio.size == 0:
        return 0.0

    audio_64 = audio.astype(numpy.float64, copy=False)
    return float(numpy.sqrt(numpy.mean(numpy.square(audio_64))))


def is_meaningful_transcript(text: str) -> bool:
    """Return whether a transcript contains at least one letter or digit."""
    return re.search(r"\w", text, flags=re.UNICODE) is not None
