# Installation Guide

Everything needed to run this project from a clean machine. The stack is bilingual:
**Python** (uv workspace — FastAPI, SQLAlchemy, Alembic) + **Node.js** (Next.js frontend).
PostgreSQL runs in Docker.

---

## 1. System requirements

| Tool | Min version | Purpose |
|---|---|---|
| Docker Engine | 24+ | Runs PostgreSQL (and the full stack in production) |
| Node.js | 20 LTS | Next.js dev server + `openapi-typescript` |
| uv | latest | Python workspace, virtualenv, package resolution |
| Make | any | Task runner (`make up`, `make dev`, `make test`) |

> **Not needed as system installs:** Python (uv downloads it), PostgreSQL client
> (runs in Docker), pip/virtualenv (uv replaces both).

---

## 2. Install system tools

### Docker Engine

**Linux (Ubuntu / Debian / Linux Mint):**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker          # apply group without logging out, or log out/in
```

> **Linux Mint users:** the get.docker.com script may detect Mint as Debian and
> point to the wrong repo. If the install fails, use the manual path instead:
>
> ```bash
> sudo apt-get install -y ca-certificates curl
> sudo install -m 0755 -d /etc/apt/keyrings
> sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
> sudo chmod a+r /etc/apt/keyrings/docker.asc
> echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
> sudo apt-get update
> sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin --fix-missing
> sudo usermod -aG docker $USER && newgrp docker
> ```

Verify: `docker run hello-world`

---

### Node.js 20 via nvm

nvm lets you pin the Node version per project without touching the system Node.

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Open a new shell (or `source ~/.zshrc` / `source ~/.bashrc`), then:

```bash
nvm install 20
nvm use 20
nvm alias default 20
```

Verify: `node --version` (should print `v20.x.x`)

---

### uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify: `uv --version`

---

### WeasyPrint native dependencies

WeasyPrint generates PDF invoices and requires system graphics libraries.
Install them once so `make dev` never breaks mid-feature:

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

> On macOS: `brew install pango cairo gdk-pixbuf libffi`

---

### Make

Usually pre-installed. If not:

```bash
sudo apt-get install -y make   # Linux
xcode-select --install          # macOS
```

---

## 3. Clone and set up the project

```bash
git clone <repo-url>
cd invoicing-platform
```

**Copy the environment file:**

```bash
cp .env.example .env
# Edit .env if you need non-default DB credentials
```

**Install Python workspace dependencies:**

```bash
uv sync
```

**Install frontend dependencies:**

```bash
cd apps/web && npm install && cd -
```

---

## 4. Run it

```bash
make up       # start PostgreSQL in Docker
make migrate  # run module migrations (wired in B10)
make dev      # API (uvicorn --reload) + Next.js dev server
```

- API + docs: http://localhost:8000/docs
- Web: http://localhost:3000

**Regenerate frontend types after any backend contract change:**

```bash
make gen-types   # OpenAPI → apps/web/lib/types.ts (wired in B13)
```

**Run the test suite:**

```bash
make test
```

---

## 5. Verify the install

```bash
docker --version          # Docker version 24+
docker compose version    # v2+
node --version            # v20+
uv --version
make test                 # 1 passed (health check)
make up                   # exits 0, Postgres container running
```
