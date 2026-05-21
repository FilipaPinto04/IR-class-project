# Imagem leve baseada em Python
FROM python:3.10-slim

# Definir a pasta de trabalho dentro do contentor
WORKDIR /app

# Instalar dependências essenciais do sistema (necessárias para compilar scikit-learn/numpy se preciso)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar os ficheiros de requisitos primeiro (otimização de cache do Docker)
# Nota: Garante que tens um ficheiro 'requirements.txt' na raiz com fastapi, uvicorn, scikit-learn, nltk, unidecode, pdfplumber, requests, selenium
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Descarregar recursos essenciais do NLTK (conforme configurado no teu nlp.py)
RUN python -m nltk.downloader punkt punkt_tab stopwords wordnet omw-1.4

# Copiar todo o código-fonte para dentro do contentor
COPY . .

# Expor a porta que a API vai usar
EXPOSE 8000

# Variável de ambiente para garantir que os logs do Python saem em tempo real
ENV PYTHONUNBUFFERED=1
# Configurar o PYTHONPATH para que o Python encontre o pacote 'src' na raiz
ENV PYTHONPATH=/app

# Comando corrigido para arrancar a tua API baseada no teu main.py
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]