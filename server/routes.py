from server.resources.chatbot_api import ChatBotAPI
from server.resources.session_api import CreateSession, RemoveSession, HealthCheck


def init_routes(api, session_controller):
    api.add_resource(CreateSession, '/api/sessions',
                     resource_class_kwargs={'session_controller': session_controller})
    
    api.add_resource(ChatBotAPI, '/api/sessions/<string:session_id>/ask_question',
                     resource_class_kwargs={'session_controller': session_controller})
    
    api.add_resource(RemoveSession, '/api/sessions/<string:session_id>',
                     resource_class_kwargs={'session_controller': session_controller})

    api.add_resource(HealthCheck, '/api/health_check')

