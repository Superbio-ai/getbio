from flask import Flask
from flask_cors import CORS
from flask_restful import Api
from flask_bcrypt import Bcrypt

from server.config import Config
from server.log import set_logging
from server.routes import init_routes
from server.resources.llm_controller import LLMSessionController

application = Flask(__name__)
CORS = CORS(application)
API = Api(application)
bcrypt = Bcrypt(application)

session_controller = LLMSessionController()

init_routes(API, session_controller)
set_logging(application)

############
if __name__ == "__main__":
    _ = Config()
    application.run(host='0.0.0.0', port=8000)
