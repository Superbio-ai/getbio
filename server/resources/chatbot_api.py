from flask import request
from .session_api import WrapResource


class ChatBotAPI(WrapResource):
    def __init__(self, **kwargs) -> None:
        self.session_controller = kwargs['session_controller']
        super().__init__()

    def post(self, session_id):
        try:
            question = request.json.get('question')

            if not question:
                return {"error": "Question is required."}, 500
            print("SESSION_ID: ", session_id, type(session_id))
            session_llm_controller = self.session_controller.sessions[session_id]

            database = request.json.get('database')
            wordiness = "concise"
            if not session_id or not database or not wordiness:
                return {"error": "session_id, database and wordiness are required."}, 400

            print("Question and prompt details", database, wordiness)
            return session_llm_controller.ask_question(database, wordiness)

        except KeyError as e:
            print(e)
            return {"error": "Session not found."}, 404
        except Exception as e:
            return {"error": str(e)}, 500
