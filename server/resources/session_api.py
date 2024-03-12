from flask import request
from flask_restful import Resource
import logging
from logging.handlers import WatchedFileHandler
import json


class WrapResource(Resource):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.log = 'application.log'

    @classmethod
    def set_logging(cls, log_file: str):
        handler = WatchedFileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s  [%(levelname)s]\n%(message)s",
            "%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.setLevel("INFO")
        root.addHandler(handler)


class CreateSession(WrapResource):
    def __init__(self, **kwargs) -> None:
        self.session_controller = kwargs['session_controller']
        super().__init__()

    def post(self):
        self.set_logging(self.log)
        session_id = request.json.get('session_id')
        logging.info('Create Session Post:')
        logging.info(json.dumps(request.json))

        try:
            self.session_controller.new_session(str(session_id)) #,str(role),str(language),packages,str(wordiness))
            logging.info(f'Created Session {session_id}')
            return {"message": f'Session {session_id} created successfully.'}, 200
        except Exception as e:
            return {"error": str(e)}, 500


class RemoveSession(WrapResource):
    def __init__(self, **kwargs) -> None:
        self.session_controller = kwargs['session_controller']
        super().__init__()

    def delete(self, session_id: str):
        try:
            self.session_controller.remove_session(str(session_id))
            logging.info(f'Removed session {session_id}')
            return {"message": f'Session {session_id} removed successfully.'}, 200
        except Exception as e:
            return {"error":  f'Session {session_id} not found.'}, 500


class HealthCheck(Resource):
    def get(self):
        pass
