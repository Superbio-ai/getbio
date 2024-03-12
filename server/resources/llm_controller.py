import os
from datetime import datetime, timedelta
from consts import MAX_NEW_TOKENS, MAX_TOKENS
import gc

import openai
import time

# read Open AI API key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")
model = "gpt-4-0613"


class LLMSessionController:
    def __init__(self) -> None:
        self.sessions = {}

    def new_session(self, session_id): #, role, language, packages, wordiness):
        if session_id in self.sessions.keys():
            print("DELETING")
            session = self.sessions[session_id]
            self.remove_session(session_id)

        self.clean_sessions()
        session = LLMController(session_id) #, role, language, packages, wordiness)
        self.sessions[session_id] = session

    def clean_sessions(self):
        remove_uid = []
        for uid in self.sessions.keys():
            session = self.sessions[uid]
            diff = datetime.now() - session.last_used_time
            if diff > timedelta(hours=12):
                remove_uid.append(uid)
        for uid in remove_uid:
            self.remove_session(uid)

    def remove_session(self, uid):
        print("REMOVE SESSION")
        print("SESSIONS: ", self.sessions.keys())
        session = self.sessions[uid]
        del self.sessions[uid]
        gc.collect()
        
        
class LLMController:
    def __init__(self, sid, database: str = 'unspecified', task: str = 'unspecified', wordiness: str = 'concise') -> None:
        self.sid = str(sid)
        self.langchain_dir = f"/app/chat_history/{self.sid}"
        self.last_used_time = datetime.now()       #updated when used
        self.user_messages = []
        self.responses = []
        self.messages = []
        self.max_new_tokens = MAX_NEW_TOKENS
        self.max_tokens = MAX_TOKENS          # for gpt 4 #
        self.status = 'ready'
        self.tokens_left = MAX_TOKENS
        self.prompt = self.prepare_prompt(database, task, wordiness)
    
    def prepare_prompt(self, database, task, wordiness):
        self.prompt = f'''Provide me with a python gget command to query {database} for task {task}.
        Provide {wordiness} responses, and include code.
        Respond to questions which are not related to using gget with 'Sorry I can only help with querying biological databases'.'''
        
        
    def prepare_messages(self):
        if abs(len(self.user_messages)-len(self.responses))>1:
            raise ValueError("User messages and responses are not similar length")
        messages=[{"role": "system", "content": self.prompt}]
        for i in range(len(self.user_messages)):
            messages.append({"role": "user", "content": self.user_messages[i]})
            if i<len(self.responses):
                messages.append({"role": "assistant", "content": self.responses[i]})
        
        self.messages = messages
        #self.status = status
        #self.tokens_left = tokens_left
        
    
    def comp(self, outputs=1, temperature = 0.75, attempts = 3, follow_up = True):
        messages_to_api = self.messages.copy()
        for i in range(attempts):
            try:
                response = openai.ChatCompletion.create(
                model=model,
                messages = messages_to_api,
                n=outputs,
                temperature = temperature
                )
                # Get the response text from the API response
                if outputs == 1:
                    response_text = response['choices'][0]['message']['content']
                else:
                    response_text = []
                    for i in range(outputs):
                        response_text.append(response['choices'][i]['message']['content'])
                
                self.responses.append(response_text)
                # add response to messages
                messages_to_api.append({"role": "assistant", "content": response_text})
                follow_up_text = ''
                if follow_up:
                    messages_to_api.append({"role": "user", "content": "What are some follow-up queries I might run, which would use python gget? Please provide answers in natural language. Keep answer brief and limit to 3 max"})
                    follow_up_text = openai.ChatCompletion.create(
                    model=model, messages = messages_to_api, n=1, temperature = temperature
                    )
                return response_text, follow_up_text['choices'][0]['message']['content']
            
            except openai.error.APIConnectionError and (i < (attempts-1)):
                print("Hang on, this is taking longer than usual. Retrying...")
                time.sleep(10) # Wait for 5 seconds before retrying
                
                
    def ask_question(self, question, database: str = 'unspecified', task: str = 'unspecified', wordiness: str = 'concise'):
        self.prepare_prompt(database, task, wordiness)
        self.user_messages.append(question)
        self.prepare_messages()
        
        try:
            response_message, follow_up_text = self.comp()
            return {'answer': response_message, 'follow_up_suggestions': follow_up_text}, 200
        except openai.error.InvalidRequestError as e:
            return {"error": str(e)}, 502
        except openai.error.APIConnectionError as e:
            return {"error": str(e)}, 503
        except Exception as e:
            return {"error": str(e)}, 500


class ChatBot:
    def __init__(self, database: str = 'unspecified', task: str = 'unspecified', wordiness: str = 'concise') -> None:
        self.user_messages = []
        self.responses = []
        self.messages = []
        self.max_new_tokens = MAX_NEW_TOKENS
        self.max_tokens = MAX_TOKENS          # for gpt 4
        self.status = 'ready'
        self.tokens_left = MAX_TOKENS
        
        self.prompt = f'''Provide me with a python gget command to query {database} for task {task}.
        Provide {wordiness} responses, and include code.
        Respond to questions which are not related to using gget with 'Sorry I can only help with querying biological databases'.'''
        
    def prepare_messages(self):
        if abs(len(self.user_messages)-len(self.responses))>1:
            raise ValueError("User messages and responses are not similar length")
        messages=[{"role": "system", "content": self.prompt}]
        for i in range(len(self.user_messages)):
            messages.append({"role": "user", "content": self.user_messages[i]})
            if i<len(self.responses):
                messages.append({"role": "assistant", "content": self.responses[i]})
                
        token_count = sum([len(m['content']) for m in messages])

        # Tokens left to use
        tokens_left = self.max_tokens - token_count
        
        if tokens_left <= 0:
            # If close to the max token limit, start a new conversation
            messages = messages[-2:]  # keep last user and assistant message
            status = "restart"
            token_count = sum([len(openai.api.encode(m['content'])) for m in messages])
            tokens_left = self.max_tokens - token_count
        else:
            status = "continue"
        
        self.messages = messages
        self.status = status
        self.tokens_left = tokens_left
    
    def comp(self, outputs=1, temperature = 0.75, attempts = 3, follow_up = True):
        messages_to_api = self.messages.copy()
        for _ in range(attempts):
            try:
                response = openai.ChatCompletion.create(
                model=model,
                messages = messages_to_api,
                n=outputs,
                temperature = temperature
                )
                # Get the response text from the API response
                if outputs == 1:
                    response_text = response['choices'][0]['message']['content']
                else:
                    response_text = []
                    for i in range(outputs):
                        response_text.append(response['choices'][i]['message']['content'])
                
                self.responses.append(response_text)
                follow_up_text = ''
                if follow_up:
                    messages_to_api.append({"role": "user", "content": "What are some follow-up queries I might run, which would use python gget? Please provide answers in natural language. Keep answer brief and limit to 3 max"})
                    follow_up_text = openai.ChatCompletion.create(
                    model=model, messages = messages_to_api, n=1, temperature = temperature
                    )
                return response_text, follow_up_text['choices'][0]['message']['content']
            
            except openai.error.APIConnectionError:
                print("Hang on, this is taking longer than usual. Retrying...")
                time.sleep(5) # Wait for 5 seconds before retrying
    
    def ask_question(self, question):
        if not question:
            return {"error": "question is required."}, 400
        self.user_messages.append(question)
        self.prepare_messages()
        response_message, follow_up_text = self.comp()
        return response_message, follow_up_text, 500
    