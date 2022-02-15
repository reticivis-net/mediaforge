# used by improcessing.tts() on windows becuse espeak sucks on windows
Add-Type -AssemblyName System.Speech;
$synth = (New-Object System.Speech.Synthesis.SpeechSynthesizer);
$synth.SelectVoiceByHints($args[2])
$synth.SetOutputToWaveFile($args[0]);
$synth.Speak($args[1]);