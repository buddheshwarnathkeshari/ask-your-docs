# Ask Your Docs: Enterprise Retrieval-Augmented Generation (RAG) System

## Project Summary

**Ask Your Docs** is a full-stack, end-to-end **Retrieval-Augmented Generation (RAG) system** designed to provide accurate, context-aware Q&A capabilities over proprietary and unstructured document corpora.

This project demonstrates expertise in building complex, distributed, and scalable AI applications by leveraging cutting-edge components in a robust microservices architecture.

## Key Features

* **Contextual Q&A:** Answers user queries by retrieving contextually relevant data chunks from an indexed corpus, drastically reducing LLM hallucinations.
* **Scalable RAG Pipeline:** Utilizes **Gemini 1.5 Flash LLM** for generation and **Qdrant (Vector Database)** for high-performance vector indexing and low-latency similarity search.
* **Asynchronous Ingestion:** Employs **Celery** and **Redis** for asynchronous processing of document uploads, embedding generation, and vector insertion, ensuring the main API remains highly responsive.
* **Full-Stack Interface:** A modern user interface built with **React** for seamless document management and chat interaction.
* **Containerized Environment:** Fully managed via **Docker** and `docker-compose` for consistent, one-command local environment setup.

## Technology Stack & Architecture

| Category | Component | Rationale / Use |
| :--- | :--- | :--- |
| **LLM & AI** | **Gemini 1.5 Flash** | Used for high-speed, cost-effective, and context-aware text generation. |
| **Embedding** | Google's **Text Embedding Model** | Used to generate dense vector representations of document chunks and user queries. |
| **Vector DB** | **Qdrant** | High-performance open-source vector database for vector indexing and querying. |
| **Backend** | **Python**, **Django (DRF)** | Robust framework for building scalable REST APIs, handling core application logic, and user management. |
| **Frontend** | **React** | Modern framework for building a responsive, chat-based user interface. |
| **Database** | **PostgreSQL** | Primary relational database for storing metadata, user data, and document status. |
| **Queue/Cache** | **Celery, Redis** | **Celery** for task queue management (heavy embedding jobs). **Redis** for the Celery broker. |
| **DevOps** | **Docker**, `docker-compose` | Containerization for simplified, deployment-ready development environments. |

## Local Setup and Deployment

### Prerequisites

* **Docker and Docker Compose** installed.
* A **Gemini API Key** (or an equivalent API Key for the embedding model).

### Step 1: Clone the Repository

```bash
git clone [https://github.com/buddheshwarnathkeshari/ask-your-docs.git](https://github.com/buddheshwarnathkeshari/ask-your-docs.git)
cd ask-your-docs
```
### Step 2: Configure Environment Variables

You must create a working `.env` files in backend and frontend based on the provided `backend/.env.template` and `frontend/.env.template`. This file holds the configuration and sensitive API keys for all your services.

1.  **Create the `.env` file** by copying the template:

    ```bash
    cp backend/env.template backend/.env && cp frontend/env.template frontend/.env
    ```

2.  **Open the new `backend/.env` file** and populate it with your actual values. A correctly configured file based on your project details should look like this (remember to replace the placeholder `GEMINI_API_KEY`):

    ```ini
    # .env file content
    # --- POSTGRES CONFIGURATION ---
    POSTGRES_HOST=postgres
    POSTGRES_PORT=5432
    POSTGRES_DB=askyourdocs
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=postgres

    # --- REDIS/CELERY CONFIGURATION ---
    REDIS_URL=redis://redis:6379/0
    CELERY_BROKER_URL=${REDIS_URL}
    CELERY_RESULT_BACKEND=${REDIS_URL}

    # --- QDRANT CONFIGURATION ---
    QDRANT_URL=http://qdrant:6333
    QDRANT_COLLECTION_NAME=documents

    # --- GEMINI/LLM CONFIGURATION ---
    GEMINI_API_KEY=<YOUR_GEMINI_API_KEY>
    GEMINI_API_URL=https://generativelanguage.googleapis.com
    GEMINI_EMBED_MODEL=embedding-001
    GEMINI_LLM_MODEL=gemini-2.0-flash-lite

    # --- SYSTEM PARAMETERS ---
    EMBED_DIM=768
    ```

### Environment Variable Key Explanations

| Key Name | Purpose | Default/Example Value | Component |
| :--- | :--- | :--- | :--- |
| `POSTGRES_HOST` | Hostname/Service name for the PostgreSQL database container. | `postgres` | Postgres / Django |
| `POSTGRES_PORT` | Port for the PostgreSQL service. | `5432` | Postgres / Django |
| `POSTGRES_DB` | Name of the database schema to use. | `askyourdocs` | Postgres / Django |
| `POSTGRES_USER` | Username for the database login. | `postgres` | Postgres / Django |
| `POSTGRES_PASSWORD` | Password for the database user. | `postgres` | Postgres / Django |
| `REDIS_URL` | Base URL for the Redis service (used by Celery). | `redis://redis:6379/0` | Redis / Celery |
| `CELERY_BROKER_URL` | URL Celery uses to connect to the message broker. | `${REDIS_URL}` | Celery |
| `CELERY_RESULT_BACKEND` | URL Celery uses to store task results. | `${REDIS_URL}` | Celery |
| `QDRANT_URL` | URL for the Qdrant vector database service. | `http://qdrant:6333` | Qdrant / Django |
| `QDRANT_COLLECTION_NAME` | The name of the collection to store vector embeddings. | `documents` | Qdrant |
| `GEMINI_API_KEY` | **REQUIRED:** Your secret API key for Gemini authentication. | `<YOUR_GEMINI_API_KEY>` | Gemini / Django |
| `GEMINI_API_URL` | The base URL for the Gemini API endpoint. | `https://generativelanguage.googleapis.com` | Gemini / Django |
| `GEMINI_EMBED_MODEL` | The specific model used for generating vector embeddings. | `embedding-001` | Gemini / Django |
| `GEMINI_LLM_MODEL` | The specific LLM used for answering questions (generation). | `gemini-2.0-flash-lite` | Gemini / Django |
| `EMBED_DIM` | The output dimension size of the chosen embedding model. | `768` | Django / Qdrant |

**Open the new `frontend/.env` file** and populate it with your actual values. A correctly configured file based on your project details should look like this 

```
REACT_APP_API_BASE=http://localhost:8000
```
| Key Name | Purpose | Default/Example Value | Component |
| :--- | :--- | :--- | :--- |
| `REACT_APP_API_BASE` | REQUIRED: The base URL where the React application sends API requests to the Django backend. | `http://localhost:8000` | React / Django |

### Step 3: Build and Run Services
Use docker-compose to build the images and launch all services (Postgres, Qdrant, Redis, Backend, Frontend) in detached mode.

```docker-compose up --build -d```

### Step 4: Database Setup and Initialization
```
# Enter the Django service container (The service name may vary, check your docker-compose.yml)
docker exec -it askyourdocs_backend bash 

# Run Django migrations
python manage.py makemigrations
python manage.py migrate

# Optional: Create a superuser
python manage.py createsuperuser

# Exit the container
exit
```

### Step 5: Access the Application
Once all services are healthy and running:
* Frontend (React): http://localhost:3000

* Backend (Django API): http://localhost:8000

* Admin (Django Admin): http://localhost:8000/admin (Monitor your DB models here)

* Qdrant UI Dashboard: http://localhost:6333/dashboard (Monitor your vector collections here)

