# 🏥 E2E Clinical Scribe Backend (Feature Compete)

> **A High-Performance, Privacy-First Clinical Documentation Backend built for T4 GPUs.**

This project implements a complete **end-to-end LLMOps pipeline** for real-time clinical scribing. It orchestrates state-of-the-art models to transcribe doctor-patient conversations, infer speaker roles, mask sensitive PII, and generate structured SOAP notes incrementally—all optimized to run efficiently on limited hardware resources (e.g., NVIDIA T4).

-----

## 🚀 Key Features

### 1\. **Real-Time Audio Ingestion Pipeline**

  * **Streaming Support:** Processes audio chunks (30s-60s) continuously via `FastAPI`.
  * **State-of-the-Art ASR:** Utilizes **WhisperX** with forced alignment for precise word-level timestamps.
  * **Intelligent Role Inference:** A dedicated lightweight LLM agent tags speakers (Doctor/Patient) based on semantic context, overcoming diarization latency issues.

### 2\. **Clinical LLM Engine (vLLM Integration)**

  * **High-Throughput Inference:** Integrated **vLLM** (AsyncLLMEngine) directly into the backend for token generation.
  * **Incremental Updates:** Uses a smart "Delta" logic to append new information to SOAP notes without rewriting the entire history, reducing latency and cost.
  * **T4 Optimization:** Configured for `int8` quantization and aggressive VRAM management to coexist with ASR and Safety models on a single T4 GPU.

### 3\. **Robust Safety & Privacy Guardrails**

  * **PII Masking:** **Microsoft Presidio** integration to redact names, IDs, and phone numbers before data storage.
  * **Hallucination Detection:** Runs a **BERT-based Medical NER** and NLI cross-encoders in background threads to verify generated summaries against the transcript.
  * **Medical Safety Checks:** Specifically monitors the 'Plan' section for dosage errors or contraindications.

### 4\. **Feedback Loop & Data Flywheel**

  * **RLHF Ready:** Implements an `Accept` / `Reject` / `Edit` workflow for doctors.
  * **Automatic Routing:** Edits are automatically classified into **SFT** (correction) or **DPO** (preference) datasets based on edit distance logic.
  * **Redis Analytics:** Tracks similarity scores, rejection rates, and latency metrics in real-time.

### 5\. **Async & Event-Driven Architecture**

  * **Non-Blocking Guardrails:** Heavy safety checks run via `BackgroundTasks` and communicate results via **Redis Polling**, ensuring UI responsiveness.
  * **State Management:** **Redis** is used as the single source of truth for dialogue history, interim states, and atomic metric aggregation.

-----

## 🛠️ Architecture Overview

```mermaid
graph TD
    User[Frontend / Doctor] -->|Audio Chunk| API[FastAPI Backend]
    API -->|1. Transcribe| Whisper[WhisperX (CPU/GPU)]
    API -->|2. Tag Roles| Role[Role Inference LLM]
    API -->|3. Mask PII| PII[Presidio Anonymizer]
    API -->|4. Generate Note| vLLM[vLLM Engine (T4 GPU)]
    
    subgraph "Async Background Tasks"
        Guard[Guardrail Service] -->|Check Safety| Redis
        Safety[Medical Safety] -->|Check Dosage| Redis
    end
    
    API -.->|Trigger| Guard
    API -.->|Trigger| Safety
    
    vLLM -->|Incremental Update| Redis[(Redis State)]
    Redis -->|Polling| User
```

-----

## 💻 Tech Stack

  * **Framework:** FastAPI (Python 3.11+)
  * **LLM Serving:** vLLM (AsyncLLMEngine)
  * **ASR:** WhisperX
  * **Database:** Redis (State & Pub/Sub)
  * **NLP & Safety:** Spacy, HuggingFace Transformers (BERT/DeBERTa), Microsoft Presidio
  * **Infrastructure:** Optimized for NVIDIA T4 (16GB VRAM)

-----

## 🔮 Future Roadmap

I am actively working on scaling this MVP to a production-grade distributed system.

### 1\. **Observability (Prometheus & Grafana)**

  * Current status: Internal Python-based metric scraping.
  * **Plan:** Deploy a Prometheus exporter to scrape `vLLM` metrics (throughput, cache usage, queue length) for professional monitoring and alerting.

### 2\. **Distributed Concurrency Control**

  * Current status: Atomic Redis counters.
  * **Plan:** Implement **Redis Distributed Locks** (Redlock) to safely handle concurrent audio chunks arriving out-of-order or simultaneously in a scaled environment.

### 3\. **Task Queue for CPU-Heavy Loads**

  * Current status: `asyncio.to_thread` within FastAPI.
  * **Plan:** Offload heavy BERT/NER safety checks to **Celery + RabbitMQ** workers to prevent CPU starvation on the main API server.

### 4\. **Advanced PII Masking Strategy**

  * Current status: High-confidence masking.
  * **Plan:** Implement a "Medical Safety" masking logic where low-confidence PII scores are marked as `<UNCERTAIN>` rather than ignored, ensuring zero leakage risk.

### 5\. **Frontend Development**

  * Current status: Headless API.
  * **Plan:** Build a reactive UI (Streamlit) that supports real-time streaming updates, red-lining for guardrail warnings, and an intuitive feedback interface.

-----

## ⚠️ Hardware Requirements

This project is specifically designed and tuned for **Cost-Effective Inference**.

  * **Target GPU:** NVIDIA T4 (16GB VRAM) or equivalent (A10g, L4).
  * **Optimization:**
      * vLLM GPU Utilization is capped at **85%** to reserve memory for WhisperX.
      * Safety models are offloaded to CPU or quantized where possible.
      * **Note:** Running on smaller GPUs requires aggressive quantization (AWQ/GPTQ) or offloading modules.

-----

## 🚀 Getting Started

1.  **Prerequisites**

      * NVIDIA Driver & CUDA 12.1+
      * Redis Server running locally or remotely.

2.  **Installation**

    ```bash
    # Install dependencies using uv (recommended) or pip
    pip install -r requirements.txt
    ```

3.  **Configuration**

      * Create a `.env` file based on `config.py`:

    <!-- end list -->

    ```env
    TARGET_MODEL="unsloth/Llama-3-8b-Instruct"
    HF_TOKEN="your_huggingface_token"
    REDIS_HOST="localhost"
    ```

4.  **Run Server**

    ```bash
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
    ```

-----

## 📄 License

[MIT License](https://www.google.com/search?q=LICENSE)