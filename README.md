## Getting Started

First, set up the python env:

```bash
python3 -m venv venv

source venv/bin/activate
```

If fastapi is not installed, run:
```bash
pip install "fastapi" "uvicorn[standard]" "python-dotenv"
```

Then to start the backend services:
```bash
uvicorn main:app --reload --port 4000
```
