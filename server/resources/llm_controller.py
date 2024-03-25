import os
from datetime import datetime, timedelta
from consts import MAX_NEW_TOKENS, MAX_TOKENS, TIMEOUT, ENTREZ_EMAIL, INITIAL_IMPORTS
import gc
import time

import re
import openai
import concurrent.futures
import sys
import io
from types import SimpleNamespace


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
    def __init__(self, sid, database: str = 'unspecified', wordiness: str = 'concise') -> None:
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
        self.prompt = self.prepare_prompt(database, wordiness)
        
        self.namespace = SimpleNamespace()
        exec(INITIAL_IMPORTS, vars(self.namespace), vars(self.namespace))
    
    def prepare_prompt(self, database, wordiness):
        self.prompt = f'''Provide me with a python gget or biopython command to query {database}.
        Provide {wordiness} responses, and include code.
        My etrez email is "smorgan@superbio.ai"
        If using biopython then return 10 maximum results.
        Print any results to screen.
        Respond to questions which are not related to using gget or biopython with 'Sorry I can only help with querying biological databases'.'''
        
        
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
                    messages_to_api.append({"role": "user", "content": "What are some follow-up queries I might run, which would use python gget or biopython? Please provide answers in natural language. Keep answer brief and limit to 3 max"})
                    follow_up_text = openai.ChatCompletion.create(
                    model=model, messages = messages_to_api, n=1, temperature = temperature
                    )
                return response_text, follow_up_text['choices'][0]['message']['content']
            
            except openai.error.APIConnectionError and (i < (attempts-1)):
                print("Hang on, this is taking longer than usual. Retrying...")
                time.sleep(10) # Wait for 5 seconds before retrying
                
 
    def extract_code(response):
        code_pattern = r'```(.*?)```'
        # Use re.findall to extract code blocks
        code_blocks = re.findall(code_pattern, response, re.DOTALL)
        string_out = ''''''
        for i, code_block in enumerate(code_blocks, 1):
            string_out = string_out + f"{code_block.replace('python','')}\n"
        return(string_out)
    
    
    def exec_output(self, code_string):
        # Redirect the standard output to the StringIO object
        original_stdout = sys.stdout
        output_buffer = io.StringIO()
        sys.stdout = output_buffer
        namespace = self.namespace
        
        #execute code
        for attempt in range(3):
            try:
                exec(code_string, vars(namespace), vars(namespace))
                break
            except Exception as e:
                if attempt<2:
                    user_message = f"An error occurred when I tried to run that code. {e}. Can you provide an alternative executable example? Do not apologise, forget previous responses and save to the appropriate directory: DO NOT create or save to subdirectories!"
                    self.user_messages.append(user_message)
                    self.prepare_messages()
                    response, follow_up = self.comp()
                    code_string = self.extract_code(response)
                else:
                    captured_output = "I'm sorry, an error occurred when attempting to run the auto generated code (three attempts were made). Rewording your request and providing more information may help."
        # Get the captured output as a string
        captured_output = output_buffer.getvalue()
        sys.stdout = original_stdout
        output_buffer.close()
    
        return(captured_output)

               
    def ask_question(self, question, database: str = 'unspecified', wordiness: str = 'concise'):
        self.prepare_prompt(database, wordiness)
        self.user_messages.append(question)
        self.prepare_messages()
        
        try:
            response, follow_up = self.comp()
            code = self.extract_code(response)
            #run code if found, and send output to middle pane
            if len(code)>1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.exec_output, code)
                    print_out = future.result(timeout=TIMEOUT)
                    print_out = print_out.replace(ENTREZ_EMAIL, "A.N.Other@example.com")
            return {'answer': print_out, 'follow_up_suggestions': follow_up}, 200
        except openai.error.InvalidRequestError as e:
            return {"error": str(e)}, 502
        except openai.error.APIConnectionError as e:
            return {"error": str(e)}, 503
        except Exception as e:
            return {"error": str(e)}, 500