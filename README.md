## Getting Started

First, set up the python env:

```bash
python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

If fastapi is not installed, run:
```bash
pip install "fastapi" "uvicorn[standard]" "python-dotenv"
```

Then to start the backend services:
```bash
uvicorn main:app --reload --port 4000
```



## Database Setup

This only has to be done once

```bash
docker compose up -d
```

Update the ```.env```:

```DATABASE_URL=postgresql://wayfair:wayfair123@localhost:5432/wayfairstudio```