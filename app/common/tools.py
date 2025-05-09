import os
import glob
import requests
import PyPDF2
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool
from typing import Type, Any, Dict, List, Optional, ClassVar
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
)
from langchain.prompts import load_prompt
from langchain_community.chat_models import GigaChat as LangchainGigaChat
from langchain_gigachat import GigaChatEmbeddings
from app.common import AUTH_DATA, DATA_PATH, PROMPT_PATH, CYBERLENINKA_SIZE, TOP_K_PAPERS, headers, save_file, save_json, top_k_similar, logger, TIMEOUT, MODEL, SCOPE, TEMPERATURE
from gigachat import GigaChat


class BibtexGeneratorInput(BaseModel):
    paper_metadata: str = Field(
        paper_metadata="Метаданные научной статьи. Например, название статьи и автор"
    )

class BibtexGeneratorTool(BaseTool):
    name: ClassVar[str] = "generate_paper_bibtex"
    description: ClassVar[str] = """
    Выполняет генерацию представления и оформления библиографических ссылок и цитат по содержанию статьи в виде bibtex.
    """
    args_schema: ClassVar[Type[BaseModel]] = BibtexGeneratorInput
    giga: ClassVar[LangchainGigaChat] = LangchainGigaChat(
        credentials=AUTH_DATA,
        verify_ssl_certs=False,
        timeout=TIMEOUT,
        model=MODEL,
        scope=SCOPE,
        temperature=TEMPERATURE
    )
    prompt: ClassVar[Any] = load_prompt(os.path.join(PROMPT_PATH, "bibtex.yaml"))
    chain: ClassVar[Any] = prompt | giga
    return_direct: ClassVar[bool] = True

    def _run(
        self,
        paper_metadata: str="",
        run_manager=None,
    ) -> str:
        logger.info(f"Paper metadata: {paper_metadata}")

        result = self.chain.invoke(
            {
                "metadata": paper_metadata
            }
        ).content

        return {
           "markdown": result,
           "metadata": paper_metadata,
        }
        
class SearchInput(BaseModel):
    search_query_general: str = Field(
        description="упрощённый поисковый запрос пользователя"
    )
    search_query_raw: str = Field(
        description="исходный поисковый запрос пользователя"
    )

class PDFReaderInput(BaseModel):
    pdf_url: str = Field(
        description="ссылка на PDF документ"
    )

class PDFReaderTool(BaseTool):
   name: ClassVar[str] = "pdf_reader"
   description: ClassVar[str] = """
    Выполняет загрузку и "чтение" PDF документа  научной статьи на основе найденной ссылки.
    Текст, полученный из PDF используется для ответа на вопросы по данному документу (научной статье)

    Входным параметром является URL статьи, она конструируется следующим образом:

    "https://cyberleninka.ru" + LINK + "/pdf" или другая ссылка отправляется ссылка https://...

    **Если ссылка не найдена, запроси у пользователя в явном виде!**

    Пример LINK "/article/n/nazvaniye-dokumenta"

    На выходе отдаём краткое содержание файла и сам файл
    """
   args_schema: ClassVar[Type[BaseModel]] = PDFReaderInput
   return_direct: ClassVar[bool] = True
   prompt: ClassVar[Any] = load_prompt(os.path.join(PROMPT_PATH, "summary.yaml"))

   def _run(
        self,
        pdf_url: str="",
        run_manager=None,
    ) -> str:
        logger.info(f"PDF URL: {pdf_url}")

        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as errh:
            logger.error(f"Http Error: {errh}")
            return {
                "markdown": "Ошибка при загрузке PDF: HTTP ошибка",
                "metadata": ""
            }
        except requests.exceptions.ConnectionError as errc:
            logger.error(f"Error Connecting: {errc}")
            return {
                "markdown": "Ошибка при загрузке PDF: Ошибка соединения",
                "metadata": ""
            }
        except requests.exceptions.Timeout as errt:
            logger.error(f"Timeout Error: {errt}")
            return {
                "markdown": "Ошибка при загрузке PDF: Превышено время ожидания",
                "metadata": ""
            }
        except requests.exceptions.RequestException as err:
            logger.error(f"Something went wrong with the request: {err}")
            return {
                "markdown": "Ошибка при загрузке PDF: Неизвестная ошибка",
                "metadata": ""
            }

        try:
            # download and read the file
            with open('temp.pdf', 'wb') as f:
                f.write(response.content)

            with open('temp.pdf', 'rb') as pdf_file:
                read_pdf = PyPDF2.PdfReader(pdf_file)
                number_of_pages = len(read_pdf.pages)
                text = ""
                for page_number in range(number_of_pages):   
                    page = read_pdf.pages[page_number]
                    text += page.extract_text()

            # Получаем глобальный экземпляр GigaChat
            from app.common import giga

            # Формируем промпт для суммаризации
            prompt = f"""Прочитай следующий текст научной статьи и предоставь краткое содержание:

            {text[100:600] + text[-600:-100]}

            Пожалуйста, выдели основные моменты, ключевые идеи и выводы."""

            # Получаем ответ от GigaChat
            logger.info("Sending text to GigaChat for summarization")
            response = giga.chat(prompt)
            logger.info("Received summary from GigaChat")

            return {
                "markdown": response.choices[0].message.content,
                "metadata": text,
            }
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return {
                "markdown": "Ошибка при обработке PDF файла",
                "metadata": ""
            }
        finally:
            # Cleanup temporary file
            if os.path.exists('temp.pdf'):
                try:
                    os.remove('temp.pdf')
                except Exception as e:
                    logger.error(f"Error removing temporary file: {e}")

class SearchPaperTool(BaseTool):
    name: ClassVar[str] = "paper_search"
    description: ClassVar[str] = "Поиск научных статей по заданному запросу. Используется только для поиска статей, не для их анализа или суммаризации."

    def _run(self, query: str) -> str:
        try:
            from app.common import giga

            # Формирование запроса
            prompt = f"""Найди научные статьи по запросу: {query}
            Верни только список статей в формате:
            1. Название статьи
            Авторы
            Год публикации
            DOI или ссылка
            Краткое описание (2-3 предложения)

            2. [следующая статья...]"""

            # Получение ответа
            logger.info(f"Sending search query: {query}")
            response = giga.chat(prompt)
            logger.info("Received response from GigaChat")
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error in paper search: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
            return f"Ошибка при поиске статей: {str(e)}"

    def _arun(self, query: str) -> str:
        raise NotImplementedError("Async not implemented")