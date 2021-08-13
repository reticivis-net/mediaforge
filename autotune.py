from struct import pack
from wave import open

import AutoTune
import numpy as np


def autotune(IN: str, OUT: str, CONCERT_A: float = 440, FIXED_PITCH: float = 0.0, FIXED_PULL: float = 0.1,
             KEY: str = "c", CORR_STR: float = 1.0, CORR_SMOOTH: float = 0.0, PITCH_SHIFT: float = 0.0,
             SCALE_ROTATE: int = 0, LFO_DEPTH: float = 0.0, LFO_RATE: float = 1.0, LFO_SHAPE: float = 0.0,
             LFO_SYMM: float = 0.0, LFO_QUANT: int = 0, FORM_CORR: int = 0, FORM_WARP: float = 0.0,
             MIX: float = 1.0, CHUNK: int = 4096):
    """
    Autotunes a WAV file using PyAutoTune/Autotalent
    adapted from https://github.com/ederwander/PyAutoTune/blob/master/Examples/TuneAndSaveToFile.py


    :param IN: the path to the input file. must be single channel WAV file.
    :param OUT: the path to the output file.
    :param CONCERT_A: CONCERT A:
        Value in Hz of middle A, used to tune the entire algorithm.
    :param FIXED_PITCH: FIXED PITCH:
        Pitch (semitones) toward which pitch is pulled when PULL TO FIXED PITCH is engaged.
        FIXED PITCH = O: middle A.
        FIXED PITCH = MIDI pitch - 69.
    :param FIXED_PULL: PULL TO FIXED PITCH:
        Degree to which pitch Is pulled toward FIXED PITCH.
        O: use original pitch.
        1: use FIXED PITCH.
    :param KEY: the key in which it is tuned to. can be any letter a-g, A-G, or X (chromatic scale).
        internally it defines NOTES in SCALE:
        Specifies to various parts of the algorithm whether each note is: not in the scale (-1), in the scale (O), or
        in the scale and snapped toward (1).
    :param CORR_STR: CORRECTION STRENGTH:
        Strength of pitch correction.
        O: no correction.
        1: full correction.
    :param CORR_SMOOTH: CORRECTION SMOOTHNESS:
        Smoothness of transitions between notes when pitch correction is used.
        O: abrupt transitions.
        1: smooth transitions.
    :param PITCH_SHIFT: PITCH SHIFT:
        Number of notes in scale by which output pitch Is shifted.
    :param SCALE_ROTATE: OUTPUT SCALE ROTATE:
        Number of notes by which the output scale Is rotated In the conversion back to semitones from scale notes. Can
        be used to change the scale between major and minor or to change the musical mode.
    :param LFO_DEPTH: LFO DEPTH:
        Degree to which low frequency oscillator (LFO) Is applied.
    :param LFO_RATE: LFO RATE:
        Rate (In Hz) of LFO.
    :param LFO_SHAPE: LFO SHAPE:
        Shape of LFO waveform.
        -1: square.
        0: sine.
        1: triangle.
    :param LFO_SYMM: LFO SYMMETRY:
        Adjusts the rise/fall characteristic of the LFO waveform.
    :param LFO_QUANT: LFO QUANTIZATION:
        Quantizes the LFO waveform, resulting in chiptune-like effects.
    :param FORM_CORR: FORMANT CORRECTION:
        Enables formant correction, reducing the "chipmunk effect" In pitch shifting.
    :param FORM_WARP: FORMANT WARP:
        Warps the formant frequencies. Can be used to change gender/age.
    :param MIX:
        Blends between the modified signal and the delay-compensated Input signal.
        1: wet.
        O: dry.
    :param CHUNK: size of chunks of audio.
    :return: OUT
    """

    assert CONCERT_A > 0, "Concert A must be greater than 0."
    assert 0 <= FIXED_PULL <= 1, "PULL TO FIXED PITCH must be between 0 and 1."
    # https://github.com/ederwander/PyAutoTune/blob/5438fe25bf2d8458c5e2a3dfcce5f3eb1ee7340e/autotalent.c#L562-L744
    assert KEY in ["a", "A", "b", "B", "c", "C", "d", "D", "e", "E", "f", "F", "g", "G", "X"], "Invalid KEY"
    assert 0 <= CORR_STR <= 1, "CORRECTION STRENGTH must be between 0 and 1."
    assert 0 <= CORR_SMOOTH <= 1, "CORRECTION SMOOTHNESS must be between 0 and 1."
    assert -1 <= LFO_SHAPE <= 1, "LFO SHAPE must be between -1 and 1."
    assert 0 <= MIX <= 1, "MIX must be between 0 and 1."
    assert CHUNK > 0, "CHUNK must be greater than 0."
    wf = open(IN, 'rb')

    # If Stereo
    assert wf.getnchannels() == 1, "Only mono files are allowed!"

    signal = wf.readframes(-1)
    FS = wf.getframerate()
    scale = 1 << 15
    intsignal = np.frombuffer(signal, dtype=np.int16)
    floatsignal = np.float32(intsignal) / scale

    ####Setup to Write an Out Wav File####

    fout = open(OUT, 'w')
    fout.setnchannels(1)  # Mono
    fout.setsampwidth(2)  # Sample is 2 Bytes (2) if int16 = short int
    fout.setframerate(FS)  # Sampling Frequency
    fout.setcomptype('NONE', 'Not Compressed')

    for i in range(0, len(floatsignal), CHUNK):

        SignalChunk = (floatsignal[i:i + CHUNK])
        if i + CHUNK > len(floatsignal):
            CHUNK = len(SignalChunk)
        rawfromC = AutoTune.Tuner(SignalChunk, FS, CHUNK, SCALE_ROTATE, LFO_QUANT, FORM_CORR, CONCERT_A, FIXED_PITCH,
                                  FIXED_PULL, CORR_STR, CORR_SMOOTH, PITCH_SHIFT, LFO_DEPTH, LFO_RATE, LFO_SHAPE,
                                  LFO_SYMM, FORM_WARP, MIX, KEY.encode())
        shortIntvalues = np.int16(np.asarray(rawfromC) * scale)
        outdata = pack("%dh" % len(shortIntvalues), *shortIntvalues)
        fout.writeframesraw(outdata)

    # close write wav
    fout.close()
