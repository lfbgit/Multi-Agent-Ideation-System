# To install required packages:
# pip install panel openai==1.3.6 panel==1.3.4
# pip install git+https://github.com/microsoft/autogen.git



import autogen
import panel as pn
import openai
import os
import time
import asyncio
from autogen import config_list_from_json, agent_utils
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from openai import OpenAI
import json

#Disable the use of docker to run in venv.
os.environ["AUTOGEN_USE_DOCKER"] = "False"

#Set UI Template
template = pn.template.FastListTemplate(
    title="Multi-Agent Ideator",
    header_background="#2F454F",
    accent_base_color="#2F454F",
)

#APIKey update & UI
title_API_key = '1. Enter your API key'

passwordinput_API_key = pn.widgets.PasswordInput(
    name='Your OpenAI API Key',
    placeholder='Enter your API Key here',
    value= "Examplary API Key"
)

def update_environment_variable_API_key(event):
    os.environ['OPENAI_API_KEY'] = event.new

    #print("API Key updated to: " + os.environ['OPENAI_API_KEY'])


passwordinput_API_key.param.watch(
    update_environment_variable_API_key,
    'value'
)

delete_API_key_button = pn.widgets.Button(
    name="Delete API Key",
    button_type="danger"
)
def delete_API_key(event):
    del os.environ["OPENAI_API_KEY"]
    #print("API key env deleted.")
delete_API_key_button.on_click(delete_API_key)

API_app = pn.Column(
    pn.pane.Markdown(title_API_key),
    passwordinput_API_key,
    delete_API_key_button,
    sizing_mode='stretch_width',
    min_height=100
)

input_future = None
initiate_chat_task_created = False
file_is_uploaded = False

#Set default config in environment.
default_config = {
    'userproxy': {
        'name': 'Admin',
        'system_msg':'',
        'description' : ''
                        'The Admin interacts with the Planner, Problem_definer, Brainstormer, Idea_developer, Evaluator and Reporter to give feedback and request changes. '
                        'The Admin interacts with the assistant to retrieve information from files.'
                        'The Admin gives approval or requests changes for all approval requests.',
        'temp': 0.0
    },
    'gpt_assistant': {
        'name': 'assistant',
        'system_msg': ''
                      'assistant. '
                      'You are adapt at question answering and direct your response to the questioner. '
                      'You can retrieve information from your files.'
                      'You do not need to ask for permission to retrieve files.'
                      'You cannot brainstorm, develop or evaluate ideas yourself.',
        'description': ''
                       'This agent retrieves information from files. '
                       'This agent cannot brainstorm ideas, develop ideas or evaluate.',
        'temp': 0.0
    },
    'Planner': {
        'name': 'Planner',
        'system_msg': ''
                      'Planner. '
                      'You always create a plan based upon this structure: '
                      '1. Problem Definition, '
                      '2. Brainstorming, '
                      '3. Idea Development, '
                      '4. Evaluation, '
                      '5. Report. '
                      'The plan may involve six agents who do not write code: '
                      '1. Problem_Definer: Defines the problem to be solved. '
                      '2. assistant: Retrieves data from documents. '
                      '3. Brainstormer: Comes up with ideas. '
                      '4. Idea_developer: Develops ideas by adding additional detail and merges similar ideas. '
                      '5. Evaluator: Evaluates ideas against a problem definition. '
                      '6. Reporter: Creates a final report of all ideas and the process. '
                      'Each step should also include getting admin approval. '                      
                      'Explain the plan first and be clear which step is performed by which agent.'
                      'You revise the plan based on feedback from Admin, until you get admin approval. ',
        'description': ''
                       'The Planner agent creates a plan to conduct an ideation session. ',
        'temp': 0.0
    },
    'Problem_Definer': {
        'name': 'Problem_Definer',
        'system_msg': ''
                      'Problem_Definer. '
                      'You define the problem and come up with the requirements for a valid solution of the problem. '
                      'Report the problem description followed by a list of the requirements. '
                      'If additional data is required you can ask the assistant for information. '
                      'You only follow an approved plan, and must get Admin approval of your problem definition.',
        'description': ''
                       'This agent defines the problem description and comes up with solution requirements. '
                       'This agent only follows an approved plan and only answers during the problem definition step.',
        'temp': 0.0
    },
    'Brainstormer': {
        'name': 'Brainstormer',
        'system_msg': ''
                      'Brainstormer. '
                      'You have the ability to brainstorm. '
                      'You use the problem definition created by the Problem_Definer and data from the assistant to define your brainstorming activities. '
                      'You need to ask the assistant for further data. '
                      'You answer with a list of brainstormed ideas. '
                      'You only follow an approved plan and must get for Admin approval of your ideas.',
        'description': ''
                       'The Brainstomer can brainstorm new ideas. '
                       'This agent can also iterate on ideas and incorporate feedback from the Admin'
                       'This agent only follows an approved plan and only answers during the brainstorming step.',
        'temp': 0.5
    },
    'Idea_developer': {
        'name': 'Idea_developer',
        'system_msg': ''
                      'Idea_developer. '
                      'You use the list of brainstormed ideas from the Brainstormer or the Admin and develop the ideas further. '
                      'You need to ask the assistant for further data. '
                      'You try to combine and group similar ideas. '
                      'You answer with the list of ideas, followed by a short paragraph of your further development for each ideas. '
                      'You follow an approved plan and must get Admin approval of your development.',
        'description': ''
                       'The Idea_developer takes a list of ideas from the Brainstormer or the Admin and develops each idea further. '
                       'This agent also recombines similar ideas, iterates on developed ideas and incorporates feedback from the Admin. '
                       'This agent only follows an approved plan and only answers during the idea development step.',
        'temp': 0.5
    },
    'Evaluator': {
        'name': 'Evaluator',
        'system_msg': ''
                      'Evaluator. '
                      'You evaluate the ideas from the Idea_developer. '
                      'You validate that each idea meets the list of requirements set by the Problem_Definer. '
                      'You need to ask the assistant for specific information. '
                      'You clearly state which ideas fit the requirements and which do not. '
                      'You only an approved plan and must get Admin approval of your evaluation.',
        'description': ''
                       'The Evaluator evaluates the developed ideas from the Idea_developer. '
                       'This agent also iterates on their evaluation and incorporates feedback from the Admin. '
                       'This agent only follows an approved plan and only answers during the evaluation step.',
        'temp': 0.0
    },
    'Reporter': {
        'name': 'Reporter',
        'system_msg': ''
                      'Reporter. '
                      'You write a brief report of five sentences about each idea. '
                      'You must include a list of all ideas in your report.'
                      'You can ask the assistant for specific sources and add them to your report. '
                      'You only follow an approved plan and must get Admin approval of your report.',
        'description': 'The Reporter summarizes each ideas into a brief report. '
                       'The agent also iterates on the report and incorporates feedback from the Admin. '
                       'This agent only follows an approved plan and only answers during the evaluation step.',
        'temp': 0.0
    }
}
json_string_default_config = json.dumps(default_config)
os.environ["agentconfig_default"] = json_string_default_config

def load_agent_config():
    global agentconfig
    agentconfig_from_env = os.environ.get('agentconfig_saved')
    if not agentconfig_from_env:
        agentconfig_from_env = os.environ.get('agentconfig_default')
        #print("Defaulting to default agent config")
    else:
        #print("Custom agent config found.")
        pass
    if agentconfig_from_env:
        agentconfig = json.loads(agentconfig_from_env)
        #print(agentconfig_from_env) #Uncomment if you want to print the used configs to the console.

    for agent, properties in agent_widgets.items():
        properties[0].value = agentconfig[agent]["name"]
        properties[1].value = agentconfig[agent]["system_msg"]
        properties[2].value = agentconfig[agent]["description"]
        properties[3].value = agentconfig[agent]["temp"]

def create_widgets(agent_name):
    name_widget = pn.widgets.TextAreaInput(
        name=f"{agent_name} name",
        width=200,
        auto_grow=True
    )
    sysmsg_widget = pn.widgets.TextAreaInput(
        name=f"{agent_name} sysmsg",
        width=700,
        min_height=200,
        rows=6,
        auto_grow=True
    )
    description_widget = pn.widgets.TextAreaInput(
        name=f"{agent_name} description",
        width=700,
        min_height=200,
        rows=6,
        auto_grow=True
    )
    temp_widget = pn.widgets.FloatSlider(
        name=f'{agent_name} LLM temperature',
        start=0,
        end=1,
        step=0.01
    )
    return name_widget, sysmsg_widget, description_widget, temp_widget

widget_list = ['userproxy', 'gpt_assistant', 'Planner', 'Problem_Definer',
               'Brainstormer', 'Idea_developer', 'Evaluator', 'Reporter']
agent_widgets = {}
for agent in widget_list:
    agent_widgets[agent] = create_widgets(agent)

load_agent_config()

#Save Configuration in environmental var.
save_config_button = pn.widgets.Button(
    name="Save config for future sessions",
    button_type="success"
)
def save_config_values(event):
    saved_config = {
        agent: {
            "name": agent_widgets[agent][0].value,
            "system_msg": agent_widgets[agent][1].value,
            "description": agent_widgets[agent][2].value,
            "temp": agent_widgets[agent][3].value
        } for agent in widget_list
    }

    json_string_saved_config = json.dumps(saved_config)
    os.environ["agentconfig_saved"] = json_string_saved_config
    load_agent_config()
save_config_button.on_click(save_config_values)

#Delete saved config.
reset_config_button = pn.widgets.Button(name="Reset Config", button_type="danger")
def reset_config_values(event):
    del os.environ["agentconfig_saved"]
    load_agent_config()
reset_config_button.on_click(reset_config_values)

#Openai_cleanup_UI to clear all created files and gpt assistants from openai account.
def cleanup_files():
    client = OpenAI()
    file_list_response = client.files.list()
    file_list = file_list_response.data
    for file in file_list:
        if file.purpose == "assistants":
            client.files.delete(file.id)
            print(f"File deleted: {file.id}")

def cleanup_gpt_agents():
    client = OpenAI()
    assistants_list_response = client.beta.assistants.list(order="desc", limit="100")
    assistants_list = assistants_list_response.data
    for assistant in assistants_list:
        response = client.beta.assistants.delete(assistant.id)
        print(f'Agent {assistant.id} has been deleted')

def cleanup_all(event):
    cleanup_files()
    cleanup_gpt_agents()
    del os.environ["OPENAI_API_KEY"]

cleanup_button = pn.widgets.Button(
    name="Cleanup ALL files and ALL GPT assistants from OpenAI account",
    button_type="danger"
)
cleanup_button.on_click(cleanup_all)

#Create rows for Modal.
modal_title = 'Here you can modify the agent name, system_message, description, and temperature. This is only recommended for advanced users.'

modal_row_button = pn.Row(
    save_config_button,
    reset_config_button,
    cleanup_button
)

modal_row1 = pn.Row(
    agent_widgets["userproxy"][0],
    agent_widgets["userproxy"][1],
    agent_widgets["userproxy"][2]
)

modal_row2 = pn.Row(
    agent_widgets["gpt_assistant"][0],
    agent_widgets["gpt_assistant"][1],
    agent_widgets["gpt_assistant"][2],
    agent_widgets["gpt_assistant"][3]
)

modal_row3 = pn.Row(
    agent_widgets["Planner"][0],
    agent_widgets["Planner"][1],
    agent_widgets["Planner"][2],
    agent_widgets["Planner"][3]
)

modal_row4 = pn.Row(
    agent_widgets["Problem_Definer"][0],
    agent_widgets["Problem_Definer"][1],
    agent_widgets["Problem_Definer"][2],
    agent_widgets["Problem_Definer"][3]
)

modal_row5 = pn.Row(
    agent_widgets["Brainstormer"][0],
    agent_widgets["Brainstormer"][1],
    agent_widgets["Brainstormer"][2],
    agent_widgets["Brainstormer"][3]
)

modal_row6 = pn.Row(
    agent_widgets["Idea_developer"][0],
    agent_widgets["Idea_developer"][1],
    agent_widgets["Idea_developer"][2],
    agent_widgets["Idea_developer"][3]

)
modal_row7 = pn.Row(
    agent_widgets["Evaluator"][0],
    agent_widgets["Evaluator"][1],
    agent_widgets["Evaluator"][2],
    agent_widgets["Evaluator"][3]
)
modal_row8 = pn.Row(
    agent_widgets["Reporter"][0],
    agent_widgets["Reporter"][1],
    agent_widgets["Reporter"][2],
    agent_widgets["Reporter"][3]
)

accordion = pn.Accordion(
    ('userproxy', modal_row1),
    ("gpt_assistant", modal_row2),
    ("Planner", modal_row3),
    ("Problem_Definer", modal_row4),
    ("Brainstormer", modal_row5),
    ("Idea_developer", modal_row6),
    ("Evaluator", modal_row7),
    ("Reporter", modal_row8),
    toggle=True,
    width=2000
)

template.modal.extend([modal_title, modal_row_button, accordion])

def open_modal_page(event):
    if not initiate_chat_task_created:
        template.open_modal()

modal_button = pn.widgets.Button(
    name="Open Advanced Settings",
    button_type="primary"
)
modal_button.on_click(open_modal_page)
agentconfig_UI = pn.Column(
    pn.layout.Divider(),
    modal_button,
    sizing_mode = 'stretch_width'
)


# Overwrite ConversableAgent function to get async human input from UI via global var input_future
class CustomConversableAgent(autogen.ConversableAgent):
    async def a_get_human_input(self, prompt: str) -> str:
        global input_future

        #print('Async getting userinput!')  # Print status to console.

        chat_interface.send(
            prompt,
            user="MAIS",
            avatar="🌽",
            respond=False
        )

        # Create a new Future object for this input operation if none exists
        if input_future is None or input_future.done():
            input_future = asyncio.Future()

        # Wait for the callback to set a result on the future
        await input_future

        # Once the result is set, extract the value and reset the future for the next input operation
        input_value = input_future.result()
        input_future = None
        return input_value

def print_messages(recipient, messages, sender, config):
    #print(f"Messages from: {sender.name} sent to: {recipient.name} | num messages: {len(messages)} | message: {messages[-1]}")

    if messages[-1]["role"] == "user":
        if messages[-1]["name"] == agentconfig["userproxy"]["name"]:
            return False, None

    if all(key in messages[-1] for key in ['name']):
        chat_interface.send(
            messages[-1]['content'],
            user=messages[-1]['name'],
            avatar=avatar[messages[-1]['name']],
            respond=False
        )

    else:
        #Optional Agent if Agentnames don't match.
        chat_interface.send(
            messages[-1]['content'],
            user='Manager',
            avatar='💼',
            respond=False
        )
    update_total_cost()
    return False, None  # required to ensure the agent communication flow continues

async def delayed_initiate_chat(agent, recipient, message):
    global initiate_chat_task_created
    global file_is_uploaded
    global uploading
    # Indicate that the task has been created
    initiate_chat_task_created = True

    # Wait for 2 seconds
    await asyncio.sleep(2)

    # Initiate the chat async
    await agent.a_initiate_chat(recipient, message=message)

    #Cleanup for next chat.
    #Delete gpt_assistant from OpenAI
    gpt_assistant.delete_assistant()

    #delete uploaded files from OpenAI
    if llm_configRAG['file_ids'][0]:
        client.files.delete(llm_configRAG['file_ids'][0])
        print(f"Deleted file with ID: {llm_configRAG['file_ids'][0]}")

    #Reset chat and file upload.
    initiate_chat_task_created = False
    file_is_uploaded = False
    uploading.name = "No document."
    text_area.value = "."
    chat_interface.send("Your chat session has exited. Thanks for using MAIS.",
                        user="MAIS",
                        avatar="🌽",
                        respond=False)
    time.sleep(5)

async def chat_callback(contents: str, user: str, instance: pn.chat.ChatInterface):
    global initiate_chat_task_created
    global input_future
    global avatar
    global gpt_assistant
    global agentlist
    global llm_configRAG
    if file_is_uploaded == False:
        chat_interface.send("🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽"
                            "\n\nYou haven't uploaded a file yet."
                            "\nPlease upload a file."
                            "\n\n🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽🌽", user="MAIS", avatar="🌽", respond=False)
        #print("File not uploaded yet. Please upload a file.")
    else:
        if not initiate_chat_task_created:
            #print("Initating chat!")
            # LLM configurations
            llm_config_chat_manager = {
                "config_list": config_list,
                "temperature": 0,
                "timeout": 120,
                "cache_seed": 11
            }

            llm_configRAG = {
                "config_list": config_list,
                "temperature": agentconfig["gpt_assistant"]["temp"],
                "seed": 11,
                "assistant_id": assistant_id,
                "tools": [{"type": "retrieval"}],
                "file_ids": file_id
            }

            # User Proxy Configurations
            user_proxy = CustomConversableAgent(
                name = agentconfig["userproxy"]["name"],
                human_input_mode = "ALWAYS",
                code_execution_config = False,
                is_termination_msg = lambda x: x.get("content", "").rstrip().endswith("exit"),
                system_message = agentconfig["userproxy"]["system_msg"],
                description = agentconfig["userproxy"]["description"]
            )

            # GPT Assistant Configurations
            gpt_assistant = GPTAssistantAgent(
                name = agentconfig["gpt_assistant"]["name"],
                instructions = agentconfig["gpt_assistant"]["system_msg"],
                llm_config = llm_configRAG,
                description = agentconfig["gpt_assistant"]["description"]
            )
            # Agent Configurations
            Agent_planner = autogen.AssistantAgent(
                name = agentconfig["Planner"]["name"],
                human_input_mode="NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Planner"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Planner"]["system_msg"],
                description = agentconfig["Planner"]["description"]
            )

            Agent_problem_definer = autogen.AssistantAgent(
                name = agentconfig["Problem_Definer"]["name"],
                human_input_mode = "NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Problem_Definer"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Problem_Definer"]["system_msg"],
                description = agentconfig["Problem_Definer"]["description"]
            )

            Agent_brainstormer = autogen.AssistantAgent(
                name = agentconfig["Brainstormer"]["name"],
                human_input_mode = "NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Brainstormer"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Brainstormer"]["system_msg"],
                description = agentconfig["Brainstormer"]["description"]
            )

            Agent_idea_developer = autogen.AssistantAgent(
                name = agentconfig["Idea_developer"]["name"],
                human_input_mode = "NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Idea_developer"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Idea_developer"]["system_msg"],
                description = agentconfig["Brainstormer"]["description"]
            )

            Agent_evaluator = autogen.AssistantAgent(
                name = agentconfig["Evaluator"]["name"],
                human_input_mode = "NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Evaluator"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Evaluator"]["system_msg"],
                description = agentconfig["Evaluator"]["description"]
            )

            Agent_reporter = autogen.AssistantAgent(
                name = agentconfig["Reporter"]["name"],
                human_input_mode = "NEVER",
                llm_config = {
                    "config_list": config_list,
                    "temperature": agentconfig["Reporter"]["temp"],
                    "seed": 11
                },
                system_message = agentconfig["Reporter"]["system_msg"],
                description = agentconfig["Reporter"]["description"]
            )

            #create list of all agents
            agentlist = [user_proxy, Agent_planner, Agent_problem_definer, Agent_brainstormer, Agent_idea_developer,
                         Agent_evaluator, Agent_reporter, gpt_assistant]

            #define groupchat members and set max conversation rounds
            groupchat = autogen.GroupChat(
                agents = agentlist,
                messages = [],
                max_round = 30
            )
            #Define chat manager and chat manager llmconfig
            manager = autogen.GroupChatManager(
                groupchat = groupchat,
                llm_config = llm_config_chat_manager,
                #system_message = "You are a helpful Multi-Agent Ideation System. "
            )

            avatar = {user_proxy.name: "👨‍", Agent_planner.name: "💌", Agent_problem_definer.name: "❔",
                      Agent_brainstormer.name: "💡", Agent_idea_developer.name: "💭", Agent_evaluator.name: "🎚️",
                      Agent_reporter.name: "📝", gpt_assistant.name: "A"}

            #Registering replies for all agents and attaching reply function to print chat messages to chatUI
            user_proxy.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            gpt_assistant.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_planner.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_problem_definer.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_brainstormer.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_idea_developer.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_evaluator.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            Agent_reporter.register_reply(
                [autogen.Agent, None],
                reply_func = print_messages,
                config = {"chat_callback": None}
            )
            #create async task that iniates the chat via the delayed chat function.
            initiate_chat_task_created = False
            asyncio.create_task(delayed_initiate_chat(user_proxy, manager, contents))
        else:
            #listen for user input.
            if input_future and not input_future.done():
                input_future.set_result(contents)
            else:
                #print("There is currently no input being awaited.")
                pass


pn.extension(design="material")

chat_interface = pn.chat.ChatInterface(
    callback=chat_callback,
    show_button_name=False,
    sizing_mode="stretch_both",
    min_height=600,
    show_rerun= False,
    show_undo= False,
    show_clear = False
)

#Send Initatial Message to chat.
chat_interface.send("Hello, I'm MAIS a Multi-Agent Ideation System. 🌽"
                    "\nPlease read my usage guide:"
                    "\n\n🌽 1. Enter your OpenAI API key. (Optional if API key is provided.)"
                    "\n🌽 2. Upload a document containing data you want to use for ideation such as trends."
                    "\n🌽 3. Please tell me what kind of ideas you would like to ideate with me."
                    "\n\n🌽 Please note that it may take up to 20 seconds for me to reply."
                    "\n\nIf you want to start a new session, reload the page."
                    "\nAdvanced users can edit prompts at the bottom left."
                    "\nSupported extensions for file upload: .pdf, .docx, .md, .txt, .tex, .html, .pptx, .csv, .py",
                    user="MAIS",
                    avatar="🌽",
                    respond=False)

#Setup UI fields for file upload.
uploading = pn.indicators.LoadingSpinner(value=False, size=20, name='No document')
file_input = pn.widgets.FileInput(name=".pdf/.docx/.md file", accept=".pdf,.docx,.md,.txt,.tex,.html,.pptx,.py,.csv")
text_area = pn.widgets.StaticText(name='File Info', value="No file uploaded.")

# Define Callback function for file upload.
def file_callback(*events):
    global assistant_id
    global client
    global config_list
    global file_is_uploaded
    global initiate_chat_task_created
    global file_id
    if not os.environ["OPENAI_API_KEY"]:
        return

    for event in events:
        if event.name == 'filename':
            file_name = event.new
        if event.name == 'value':
            file_content = event.new

    uploading.value = True
    uploading.name = 'Uploading'
    file_path = file_name

    with open(file_path, 'wb') as f:
        f.write(file_content)
    #Set assistant_id and OpenAI client configuration
    assistant_id = os.environ.get(
        "ASSISTANT_ID",
        None
    )
    document = ''
    client = OpenAI()
    #Upload to OpenAI account.
    response = client.files.create(
        file=open(file_path, 'rb'),
        purpose='assistants'
    )

    all_files = client.files.list()
    found = False
    while not found:
        for file in all_files.data:
            if file.id == response.id:
                found = True
                print(f"Uploaded file with ID: {response.id}\n {file}")

                config_list = [
                    {
                        #'model': 'gpt-3.5-turbo-1106',
                        'model': "gpt-4-1106-preview",
                    }
                ]
                file_id = [file.id]

                text_area.value = str(client.files.retrieve(file.id))

                uploading.value = False
                uploading.name = f"Document uploaded - {file_name}"

                file_is_uploaded = True
                initiate_chat_task_created = False
                chat_interface.send(f"Thanks for uploading your file:"
                                    f"\n\n{file_name}"
                                    f"\n\n🌽 What do you want to ideate?", user="MAIS", avatar="🌽", respond=False)
                break
        if not found:
            time.sleep(5)
            all_files = client.files.list()

# Set up a callback on file input value changes
file_input.param.watch(file_callback, ['value', 'filename'])
#File Upload UI
title_fileupload = '2. Please upload your trend and context data in a single file.'
file_app = pn.Column(
    pn.layout.Divider(),
    pn.pane.Markdown(title_fileupload),
    file_input,
    uploading,
    text_area,
    sizing_mode='stretch_width',
    min_height=300
)


#Cost UI
title_cost_UI = 'Here you can see the total API costs of this session:'
text_area_cost = pn.widgets.StaticText(
    name='Total API cost in EUR',
    value = ""
)
cost_UI = pn.Column(
    pn.layout.Divider(),
    pn.pane.Markdown(title_cost_UI),
    text_area_cost,
    sizing_mode='stretch_width',
    min_height=200
)

#Get Cost Summary at the end.
def get_total_costs():
    total_cost = autogen.agent_utils.gather_usage_summary(agents=agentlist)
    total_cost_as_str = str(total_cost[0]["total_cost"])
    total_cost_as_str
    return total_cost_as_str

def update_total_cost():
    total_cost = get_total_costs()
    text_area_cost.value = total_cost
    return

template.main.extend([chat_interface])
template.sidebar.extend([API_app,file_app, cost_UI, agentconfig_UI])
template.servable()

def create_app():
    return template
main = create_app