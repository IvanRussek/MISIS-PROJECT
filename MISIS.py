import os
import streamlit as st
import requests
import uuid
import warnings
import base64
import json
import time
from app.common import steamlit_texts as TEXTS, system_prompt, giga, logger
from app.common.tools import SearchPaperTool, PDFReaderTool
from app.common import AUTH_DATA, MODEL, SCOPE, TEMPERATURE, TIMEOUT

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

logger.info(f"Initializing GigaChat with model: {MODEL}, scope: {SCOPE}")
logger.info(f"AUTH_DATA type: {type(AUTH_DATA)}")
if isinstance(AUTH_DATA, str):
    logger.info(f"AUTH_DATA length: {len(AUTH_DATA)}")
    logger.info(f"AUTH_DATA starts with: {AUTH_DATA[:20]}...")

# Hardcoded token
AUTH_DATA = "OWFkNjQyN2EtNzc1Ny00YWU0LWFjOTAtOTVkMmRiMmU5ZGZkOmEwOTllMWEyLWQwZTgtNGVjMi1hMTI3LThhYmM5OWEyMjc3YQ=="

if not AUTH_DATA:
    st.error("Ошибка: AUTH_DATA не установлен. Пожалуйста, установите переменную окружения AUTH_DATA.")
    st.stop()

try:
    auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    
    cleaned_auth_data = AUTH_DATA.strip()
    
    try:
        # Remove 'Basic ' prefix if present
        if cleaned_auth_data.startswith('Basic '):
            cleaned_auth_data = cleaned_auth_data[6:]
        
        # Decode the base64 string
        decoded_token = base64.b64decode(cleaned_auth_data).decode('utf-8')
        logger.info(f"Successfully decoded token: {decoded_token[:20]}...")
        
        # Validate the decoded token format (should be in format client_id:client_secret)
        if ':' not in decoded_token:
            raise ValueError("Decoded token must be in format 'client_id:client_secret'")
            
        client_id, client_secret = decoded_token.split(':', 1)
        if not client_id or not client_secret:
            raise ValueError("Both client_id and client_secret must be present in the token")
            
        logger.info("Token format validation successful")
        logger.info(f"Client ID length: {len(client_id)}")
        logger.info(f"Client Secret length: {len(client_secret)}")
        
    except Exception as e:
        logger.error(f"Failed to decode or validate AUTH_DATA: {e}")
        raise ValueError(f"AUTH_DATA validation failed: {str(e)}")
    
    auth_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {cleaned_auth_data}'
    }
    
    auth_payload = {
        'scope': 'GIGACHAT_API_PERS'
    }

    logger.info("Requesting access token...")
    logger.info(f"Auth URL: {auth_url}")
    logger.info(f"Auth headers: {json.dumps({k: v if k != 'Authorization' else '***' for k, v in auth_headers.items()}, indent=2)}")
    logger.info(f"Auth payload: {json.dumps(auth_payload, indent=2)}")
    
    auth_response = requests.post(
        auth_url, 
        headers=auth_headers, 
        data=auth_payload, 
        verify=False,
        timeout=30  
    )
    
    logger.info(f"Auth response status: {auth_response.status_code}")
    logger.info(f"Auth response headers: {json.dumps(dict(auth_response.headers), indent=2)}")
    logger.info(f"Auth response text: {auth_response.text}")
    
    if auth_response.status_code != 200:
        error_msg = f"Failed to get access token. Status code: {auth_response.status_code}"
        if auth_response.text:
            try:
                error_data = auth_response.json()
                error_msg += f", Error code: {error_data.get('code')}, Message: {error_data.get('message')}"
            except:
                error_msg += f", Response: {auth_response.text}"
        raise ValueError(error_msg)
    
    try:
        response_data = auth_response.json()
        access_token = response_data.get('access_token')
        if not access_token:
            logger.error(f"No access_token in response. Full response: {json.dumps(response_data, indent=2)}")
            raise ValueError("Access token not found in response")
        
        expires_in = response_data.get('expires_in')
        if expires_in:
            logger.info(f"Token will expire in {expires_in} seconds")
            
    except Exception as e:
        logger.error(f"Failed to parse access token from response: {e}")
        raise ValueError(f"Invalid response format: {auth_response.text}")

    logger.info("Successfully obtained access token")

    models_url = "https://gigachat.devices.sberbank.ru/api/v1/models"
    models_headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    logger.info("Checking available models...")
    logger.info(f"Models URL: {models_url}")
    logger.info(f"Models headers: {models_headers}")
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            models_response = requests.get(models_url, headers=models_headers, verify=False)
            logger.info(f"Models response status: {models_response.status_code}")
            
            if models_response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.info(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError("Rate limit exceeded after all retries")
            
            logger.info(f"Models response text: {models_response.text}")
            
            if models_response.status_code != 200:
                raise ValueError(f"Failed to get models. Status code: {models_response.status_code}, Response: {models_response.text}")
            
            break
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
            time.sleep(retry_delay)

    giga.credentials = f"Bearer {access_token}"
    giga.verify_ssl_certs = False
    giga.timeout = TIMEOUT
    giga.model = MODEL
    giga.scope = 'GIGACHAT_API_PERS'
    giga.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
    logger.info("GigaChat initialized successfully")

    tools = [SearchPaperTool(), PDFReaderTool()]
    logger.info("Tools created successfully")

except Exception as e:
    logger.error(f"Error initializing GigaChat: {str(e)}")
    logger.error(f"Error type: {type(e)}")
    logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
    st.error(f"Ошибка при инициализации GigaChat: {str(e)}")
    st.stop()

st.set_page_config(page_title=TEXTS.PAGE_TITLE)
st.title(TEXTS.TITLE)

st.markdown(TEXTS.HINT)

TEXTS.HR

st.markdown(TEXTS.SIDEBAR_STYLE, unsafe_allow_html=True)

with st.sidebar:
    logo_path = os.path.join("resources", "img", "logo.jpeg")
    if os.path.exists(logo_path):
        st.image(logo_path)
    else:
        st.warning("Logo image not found. Please add logo.jpeg to resources/img/ directory.")
    st.markdown(TEXTS.COMMAND_EXAMPLES)
    st.markdown(TEXTS.EXAMPLE_PAPER)

# Initialize session state with proper error handling
try:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Привет, я МИСИСИК!"}]

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "system", "content": system_prompt}]

except Exception as e:
    logger.error(f"Error initializing session state: {e}")
    st.error("Произошла ошибка при инициализации сессии. Пожалуйста, обновите страницу.")
    st.stop()

for message in st.session_state.messages:
    try:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error displaying message: {e}")
        continue

if prompt := st.chat_input("Обратитесь ко мне..."):
    if not prompt.strip():
        st.warning("Пожалуйста, введите непустое сообщение.")
        st.stop()
    
    if len(prompt) > 1000:  
        st.warning("Сообщение слишком длинное. Пожалуйста, сократите его.")
        st.stop()

    try:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt, unsafe_allow_html=True)

        with st.spinner(TEXTS.WAITING):
            with st.chat_message("assistant"):
                try:
                    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages])
                    
                    full_prompt = f"{system_prompt}\n\nИстория диалога:\n{context}\n\nПользователь: {prompt}"
                    
                    logger.info("Preparing to send message to GigaChat")
                    logger.info(f"Full prompt length: {len(full_prompt)}")
                    logger.info(f"First 100 chars of prompt: {full_prompt[:100]}...")
                    
                    try:
                        chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
                        chat_headers = {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'Authorization': f'Bearer {access_token}'
                        }
                        
                        chat_payload = {
                            "model": MODEL,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 1000
                        }
                        
                        logger.info("Sending request to GigaChat API...")
                        logger.info(f"Chat URL: {chat_url}")
                        logger.info(f"Chat headers: {json.dumps({k: v if k != 'Authorization' else '***' for k, v in chat_headers.items()}, indent=2)}")
                        logger.info(f"Chat payload: {json.dumps(chat_payload, indent=2)}")
                        
                        chat_response = requests.post(
                            chat_url,
                            headers=chat_headers,
                            json=chat_payload,
                            verify=False,
                            timeout=30
                        )
                        
                        logger.info(f"Chat response status: {chat_response.status_code}")
                        logger.info(f"Chat response headers: {json.dumps(dict(chat_response.headers), indent=2)}")
                        logger.info(f"Chat response text: {chat_response.text}")
                        
                        if chat_response.status_code != 200:
                            error_msg = f"Failed to get chat completion. Status code: {chat_response.status_code}"
                            if chat_response.text:
                                try:
                                    error_data = chat_response.json()
                                    error_msg += f", Error: {error_data.get('error', {}).get('message', chat_response.text)}"
                                except:
                                    error_msg += f", Response: {chat_response.text}"
                            raise ValueError(error_msg)
                        
                        response_data = chat_response.json()
                        if not response_data.get('choices'):
                            raise ValueError("No choices in response")
                            
                        response_text = response_data['choices'][0]['message']['content']
                        logger.info(f"Response length: {len(response_text)}")
                        logger.info(f"First 100 chars of response: {response_text[:100]}...")
                        
                    except Exception as e:
                        logger.error(f"Error in GigaChat API call: {str(e)}")
                        logger.error(f"Error type: {type(e)}")
                        logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
                        logger.error("Full error traceback:", exc_info=True)
                        raise

                    if "найди мне статьи" in prompt.lower():
                        logger.info("Using paper search tool")
                        response_text = tools[0]._run(prompt)
                    elif "прочитай эту статью" in prompt.lower() or "https://" in prompt:
                        file_path = prompt.split("https://")[-1].split()[0]
                        logger.info(f"Using PDF reader tool for file: {file_path}")
                        response_text = tools[1]._run(file_path)

                    logger.info("Adding response to session state")
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    
                    logger.info("Displaying response to user")
                    st.markdown(response_text, unsafe_allow_html=True)

                except Exception as e:
                    logger.error(f"Error in chat processing: {e}")
                    logger.error(f"Error type: {type(e)}")
                    logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
                    logger.error("Full error traceback:", exc_info=True)
                    st.error(TEXTS.SORRY)

    except Exception as e:
        logger.error(f"Error in chat processing: {e}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
        st.error(TEXTS.SORRY)
