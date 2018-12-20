import random
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./credentials.txt"

# if transcript.lower().startswith("max say"):
#     to_speech(transcript[7:len(transcript)])
# # Exit recognition if any of the transcribed phrases could be
# # one of our keywords.
# if re.search(r'\b(exit|quit)\b', transcript, re.I):
#     print('Exiting..')
#     break
#
# newsKP = ["show me the news", "open up the news", "give me the news", "what's the news like", "open news", "news"]
# if transcript.lower() in newsKP:
#     webbrowser.open("https://news.google.com/?hl=en-US&gl=US&ceid=US:en")

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

if __name__ == '__main__':
    detect_intent_texts('projectmaxwell',random.randint(1000,9999),"could you get me the news")