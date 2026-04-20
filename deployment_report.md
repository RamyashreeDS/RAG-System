# Deployment Architecture & Implementation Report

## 1. Cloud Infrastructure & Architecture
The final RAG (Retrieval-Augmented Generation) application was successfully deployed on a robust **Google Cloud Platform (GCP) Virtual Machine**. 
To ensure rapid inference speeds for our dense retrieval models, the VM was equipped with an **NVIDIA V100 Tensor Core GPU**. To support the extreme memory demands of building and storing high-dimensional vector embeddings for over 21,000 medical documents, the VM framework was upgraded to an `n1-standard-4` chassis, providing 4 vCPUs and 15 GB of dedicated system RAM.

## 2. Application Containerization 
To ensure environments were perfectly reproducible without manual setup, the entire architecture was containerized using Docker. 
A highly optimized `Dockerfile` was engineered using the official `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime` image. This allowed the stateless FastAPI webserver to seamlessly tie into the host machine’s V100 GPU natively, bypassing complex CUDA driver compilation.

## 3. Continuous Integration and Continuous Deployment (CI/CD)
To enforce professional DevOps standards, a fully automated CI/CD pipeline was constructed using **GitHub Actions**. 
- **Image Compilation:** Upon every commit pushed to the `main` branch, a GitHub Action sequentially builds the Docker image and publishes it to the GitHub Container Registry (GHCR).
- **Automated Delivery:** The pipeline securely authenticates into the GCP Virtual Machine via SSH, pulls down the latest compiled image, and executes a zero-downtime restart of the application container. 

## 4. State Persistence & Data Management
Because Docker containers are inherently ephemeral (destroying internal files during restarts), the application constantly risked losing its heavy FAISS indexes. This was successfully mitigated by mapping permanent **Docker Volumes** (`-v ~/rag_data:/app/data` and `-v ~/rag_indexes:/app/indexes`). These volumes established a direct symlink between the stateless container and the VM's permanent solid-state drive, guaranteeing that the massive 21,000 document vector database is loaded instantly upon every system reboot or code update.

## 5. Technical Troubleshooting & Optimizations
During the deployment phase, several critical architectural challenges were overcome:

* **Dependency Resolution:** A critical incompatibility between the latest HuggingFace `transformers` package and the `PyTorch 2.2.0` CUDA 12 environment was identified. This was resolved by dynamically pinning the `requirements.txt` execution context to `transformers<4.45.0`, preventing breaking API calls to non-existent PyTorch 2.4+ modules.
* **Out-of-Memory (OOM) Indexing Failures:** Generating dense vectors for a 20,000+ document corpus requires keeping millions of chunks in active memory. Initial attempts triggered Linux Kernel OOM (Out Of Memory) kills. This was bypassed by fundamentally restructuring the memory limit: allocating a 14.2 GB Linux Swapfile for hard drive overflow memory and subsequently upgrading the host VM from 1GB to 15GB of physical RAM.
* **Cloud Security Overrides:** GCP’s aggressive OS Login daemon routinely wiped the GitHub Action SSH keys from the traditional `~/.ssh/authorized_keys` file. This security hurdle was bypassed by hardcoding the public SSH keys directly into the GCP Project Metadata console ensuring a permanent, encrypted tunnel for the runner. 
* **SSL Protocol Routing:** To test the application pre-domain registration, browsers blocking HTTPS enforcement were manually bypassed by tunneling traffic strictly through standard HTTP over port `8080`.
