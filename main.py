from __future__ import division

import io
import os
import re
import sys

# Imports the Google Cloud client library
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio
from six.moves import queue

import google.cloud.texttospeech as texttospeech

from pygame import mixer

import random
import datetime
import urllib
import tempfile
import webbrowser
import dialogflow
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./credentials.txt"

ttsClient = texttospeech.TextToSpeechClient()

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

def to_speech(text):
    # os.remove("output.mp3")

    input_text = texttospeech.types.SynthesisInput(text=text)
    # Note: the voice can also be specified by name.
    # Names of voices can be retrieved with client.list_voices().
    voice = texttospeech.types.VoiceSelectionParams(
        language_code="en-GB",
        name="en-GB-Standard-B")

    audio_config = texttospeech.types.AudioConfig(
         audio_encoding=texttospeech.enums.AudioEncoding.MP3)

    response = ttsClient.synthesize_speech(input_text, voice, audio_config)
    # The response's audio_content is binary.
    # with tempfile.NamedTemporaryFile() as tmp:
    #     tmp.write(response.audio_content)
    #     tmp.seek(0)
    #     mixer.init()
    #     mixer.music.load(tmp.name)
    #     mixer.music.play()

    # with open('output.mp3', 'wb') as out:
         # out.write(response.audio_content)

    print("Max: " + text)
    song = io.BytesIO(response.audio_content)
    mixer.init()
    mixer.music.load(song)
    mixer.music.play()

    return response

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    global isListening
    isListening = False
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            transcript = transcript.strip()
            print("Heard: " + transcript + overwrite_chars)

            intents = ["affect light", "retrieve news", "wake up"]

            dialogFlowResponse = detect_intent_texts('projectmaxwell', 1, transcript)
            intent = dialogFlowResponse.intent.display_name.lower()
            to_speech(dialogFlowResponse.fulfillment_text)

            if intent == 'wake up':
                isListening = True

            # maxKeyphrases = ["hey max", "yomax", "yo max", "yo max you there", "max", "alright max", "okay max","max you there"]
            # if transcript.lower() in maxKeyphrases:
            #     isListening = True
            #     greetings = ["Hello sir!", "At your service", "Yes sir?"]
            #     greetingVal = random.randrange(len(greetings))
            #     greetingType = random.randrange(2)
            #     currTime = datetime.datetime.now().hour
            #     if greetingType == 0:
            #         if 3 < currTime < 12:
            #             to_speech("Good morning.")
            #         elif 12 <= currTime < 18:
            #             to_speech("Good afternoon.")
            #         else:
            #             to_speech("Good evening.")
            #     elif greetingType == 1:
            #         to_speech(greetings[greetingVal])

            if isListening:
                if intent == 'retrieve news':
                    webbrowser.open("https://news.google.com/?hl=en-US&gl=US&ceid=US:en")

            num_chars_printed = 0

def detect_intent_texts(project_id, session_id, text):
    """Returns the result of detect intent with texts as inputs.

    Using the same `session_id` between requests allows continuation
    of the conversation."""

    import dialogflow_v2 as dialogflow
    session_client = dialogflow.SessionsClient()

    session = session_client.session_path(project_id, session_id)
    print('Session path: {}\n'.format(session))

    # for text in texts:
    #     text_input = dialogflow.types.TextInput(
    #         text=text, language_code='en')
    #
    #     query_input = dialogflow.types.QueryInput(text=text_input)
    #
    #     response = session_client.detect_intent(
    #         session=session, query_input=query_input)
    #
    #     print('=' * 20)
    #     print('Query text: {}'.format(response.query_result.query_text))
    #     print('Detected intent: {} (confidence: {})\n'.format(
    #         response.query_result.intent.display_name,
    #         response.query_result.intent_detection_confidence))
    #     print('Fulfillment text: {}\n'.format(
    #         response.query_result.fulfillment_text))

    text_input = dialogflow.types.TextInput(
        text=text, language_code='en')

    query_input = dialogflow.types.QueryInput(text=text_input)

    response = session_client.detect_intent(
        session=session, query_input=query_input)

    print('=' * 20)
    print('Query text: {}'.format(response.query_result.query_text))
    print('Detected intent: {} (confidence: {})\n'.format(
        response.query_result.intent.display_name,
        response.query_result.intent_detection_confidence))
    print('Fulfillment text: {}\n'.format(
        response.query_result.fulfillment_text))

    return response.query_result

def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-US'  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    print("Now Listening.")
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_loop(responses)


if __name__ == '__main__':
    main()