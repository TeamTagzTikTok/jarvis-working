import os
import logging
import time
import pyttsx3
from dotenv import load_dotenv
import speech_recognition as sr
from langchain_ollama import ChatOllama, OllamaLLM
# from langchain_openai import ChatOpenAI # if you want to use openai
from langchain_core.messages import HumanMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from tools.time import get_time 

load_dotenv()

TRIGGER_WORD = "jarvis"
CONVERSATION_TIMEOUT = 30  # seconds of inactivity before exiting conversation mode

logging.basicConfig(level=logging.DEBUG) # logging

recognizer = sr.Recognizer()

print("🔊 Available microphones:\n")
for i, mic_name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"[{i}] {mic_name}")

while True:
    try:
        MIC_INDEX = int(input("\n🎙️ Select your mic index: "))
        mic = sr.Microphone(device_index=MIC_INDEX)
        break
    except (ValueError, OSError):
        print("💀 Invalid index, try again.")

# Initialize LLM
llm = ChatOllama(model="qwen3:1.7b", reasoning=False)

# Tool list
tools = [get_time]

# Tool-calling prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are Jarvis, an intelligent, conversational AI assistant. Your goal is to be helpful, friendly, and informative. You can respond in natural, human-like language and use tools when needed to answer questions more accurately. Always explain your reasoning simply when appropriate, and keep your responses conversational and concise."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

# Agent + executor
agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# TTS setup
def speak_text(text: str):
    try:
        engine = pyttsx3.init()
        for voice in engine.getProperty('voices'):
            if "jamie" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 180)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
        time.sleep(0.3)
    except Exception as e:
        logging.error(f"❌ TTS failed: {e}")

# Main interaction loop
def write():
    conversation_mode = False
    last_interaction_time = None

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            while True:
                try:
                    if not conversation_mode:
                        logging.info("🎤 Listening for wake word...")
                        audio = recognizer.listen(source, timeout=10)
                        transcript = recognizer.recognize_google(audio)
                        logging.info(f"🗣 Heard: {transcript}")

                        if TRIGGER_WORD.lower() in transcript.lower():
                            logging.info(f"🗣 Triggered by: {transcript}")
                            speak_text("Yes sir?")
                            conversation_mode = True
                            last_interaction_time = time.time()
                        else:
                            logging.debug("Wake word not detected, continuing...")
                    else:
                        logging.info("🎤 Listening for next command...")
                        audio = recognizer.listen(source, timeout=10)
                        command = recognizer.recognize_google(audio)
                        logging.info(f"📥 Command: {command}")

                        logging.info("🤖 Sending command to agent...")
                        response = executor.invoke({"input": command})
                        content = response["output"]
                        logging.info(f"✅ Agent responded: {content}")

                        print("Jarvis:", content)
                        speak_text(content)
                        last_interaction_time = time.time()

                        if time.time() - last_interaction_time > CONVERSATION_TIMEOUT:
                            logging.info("⌛ Timeout: Returning to wake word mode.")
                            conversation_mode = False

                except sr.WaitTimeoutError:
                    logging.warning("⚠️ Timeout waiting for audio.")
                    if conversation_mode and time.time() - last_interaction_time > CONVERSATION_TIMEOUT:
                        logging.info("⌛ No input in conversation mode. Returning to wake word mode.")
                        conversation_mode = False
                except sr.UnknownValueError:
                    logging.warning("⚠️ Could not understand audio.")
                except Exception as e:
                    logging.error(f"❌ Error during recognition or tool call: {e}")
                    time.sleep(1)

    except Exception as e:
        logging.critical(f"❌ Critical error in main loop: {e}")

if __name__ == "__main__":
    write()
