import os
import json
import logging
import base64
from sklearn.metrics.pairwise import cosine_similarity
from gigachat import GigaChat


def save_file(file_dir, file):
  with open(file_dir, 'w') as f:
    f.write(file)

def save_json(file_dir, file):
  with open(file_dir, 'w') as f:
    json.dump(file, f, ensure_ascii=False, indent=4)

def top_k_similar(query_embedding, embeddings, k=5):
  scores = []
  for emb in embeddings:
    scores.append(cosine_similarity([query_embedding], [emb]))
  top_k_indices = sorted(range(len(scores)), key=lambda i: scores[i])[-k:]
  return top_k_indices

if os.getenv("environment") != "production":
    from dotenv import load_dotenv
    load_dotenv("./.env")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

required_env_vars = ["AUTH_DATA"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

raw_auth_data = os.getenv("AUTH_DATA")
try:
    cleaned_token = raw_auth_data.strip().strip('"\'')
    
    try:
        base64.b64decode(cleaned_token)
        logger.info("Successfully validated base64 token")
    except Exception as e:
        logger.error(f"Invalid base64 token: {e}")
        raise ValueError("AUTH_DATA must be a valid base64 string")
    
    AUTH_DATA = cleaned_token
    
    logger.info(f"AUTH_DATA format: {type(AUTH_DATA)}")
    if isinstance(AUTH_DATA, str):
        logger.info(f"AUTH_DATA length: {len(AUTH_DATA)}")
        logger.info(f"AUTH_DATA starts with: {AUTH_DATA[:20]}...")
except Exception as e:
    logger.error(f"Error processing AUTH_DATA: {e}")
    raise ValueError("AUTH_DATA must be a valid string")

# Директории нужные
DATA_PATH = os.path.join('.', 'resources', 'data_tmp')
PROMPT_PATH = os.path.join('.', 'resources', 'prompts')

# Ensure required directories exist
for path in [DATA_PATH, PROMPT_PATH]:
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Created directory: {path}")

headers = {
    'content-type': 'application/json',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin'
}

try:
    CYBERLENINKA_SIZE = int(os.getenv("CYBERLENINKA_SIZE", "30"))
    TOP_K_PAPERS = int(os.getenv("TOP_K_PAPERS", "3"))
except ValueError as e:
    logger.error(f"Error parsing numeric environment variables: {e}")
    raise

MODEL = os.getenv("MODEL", "GigaChat-Pro-preview")
SCOPE = os.getenv("SCOPE", "GIGACHAT_API_CORP")
try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
    TIMEOUT = int(os.getenv("TIMEOUT", "600"))
except ValueError as e:
    logger.error(f"Error parsing numeric environment variables: {e}")
    raise

try:
    logger.info("Initializing global GigaChat instance...")
    giga = GigaChat(
        credentials=AUTH_DATA,
        verify_ssl_certs=False,
        timeout=TIMEOUT,
        model=MODEL,
        scope=SCOPE,
        temperature=TEMPERATURE,
        auth_url="https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    )
    logger.info("Global GigaChat instance initialized successfully")
except Exception as e:
    logger.error(f"Error initializing global GigaChat instance: {e}")
    raise

# Промпт для агента
system_prompt = """
Ты - МИСИСИК, ИИ ассистент по научной деятельности, специализирующийся на помощи исследователям и студентам в поиске и анализе научных статей.

Твои основные задачи:
1. Помощь в поиске релевантных научных статей
2. Анализ и суммаризация научных публикаций
3. Предоставление структурированной информации о статьях
4. Генерация библиографических ссылок

Доступные функции:

1. Поиск статей (paper_search):
   - Триггер: "найди мне статьи..." или "поищи статьи..."
   - Функционал: поиск научных статей по заданному запросу
   - Формат ответа:
     * Название статьи
     * Авторы
     * Год публикации
     * DOI или ссылка
     * Краткое описание (2-3 предложения)

2. Чтение статей (pdf_reader):
   - Триггер: "прочитай эту статью..." или прямая ссылка на PDF
   - Функционал: анализ PDF документа и предоставление структурированного содержания
   - Формат ответа:
     * Основные идеи и выводы
     * Ключевые термины и концепции
     * Методология исследования
     * Практическая значимость

3. Генерация BibTeX:
   - Триггер: автоматически при предоставлении информации о статье
   - Функционал: создание библиографических ссылок в формате BibTeX
   - Использует данные из диалога и метаданные статей

Правила работы:
1. Всегда проверяй наличие необходимых данных перед использованием функций
2. Используй только данные из истории диалога
3. При поиске статей фокусируйся на релевантности и актуальности
4. При анализе статей выделяй ключевые моменты и практическую значимость
5. Предоставляй структурированные и понятные ответы
6. Если запрос не покрыт функциями, используй LLM для генерации ответа

Формат ответов:
1. Для поиска статей:
   - Список статей с полной информацией
   - Краткое описание каждой статьи
   - Ссылки на полные тексты

2. Для анализа статей:
   - Структурированное содержание
   - Ключевые выводы
   - Практические рекомендации

3. Для общих вопросов:
   - Понятные и структурированные ответы
   - Ссылки на релевантные источники
   - Дополнительные рекомендации

Помни, что твоя главная задача - помочь пользователю в научной работе, предоставляя качественную и структурированную информацию.

Вот описание твоих возможностей: {description}
"""