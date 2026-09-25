FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# CPU-only PyTorch first: the default Linux wheel bundles CUDA libraries (several GB)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

# Bake the default reranker into the image so containers start without downloading it
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
# The model is in the image, so don't contact Hugging Face at startup.
# Set HF_HUB_OFFLINE=0 when switching RERANKER to a model that isn't baked in.
ENV HF_HUB_OFFLINE=1

COPY backend/ backend/
COPY frontend/ frontend/

RUN useradd --create-home litfinder && chown -R litfinder /opt/huggingface
USER litfinder

EXPOSE 5001 8000
# Secrets and settings come from the environment (see docker-compose.yml), never the image
CMD ["gunicorn", "--chdir", "backend", "--threads", "8", "--timeout", "180", "--bind", "0.0.0.0:5001", "wsgi:app"]
