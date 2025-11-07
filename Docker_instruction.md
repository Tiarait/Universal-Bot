[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner2-direct.svg)](https://vshymanskyy.github.io/StandWithUkraine/)

## ✅ Steps to Deploy Universal Bot with docker

## 1. Clone the project

```bash
git clone git@gitlab.com:tiar.develop/universal_bot.git
cd universal_bot
```

## 2. Check DOCKER

```bash
docker --version
```

### 2.1 Install DOCKER (if not installed)

```bash
sudo apt update
sudo apt install docker.io -y
sudo systemctl enable --now docker
```

## 3. Add .env content

```bash
nano .env
```
```bash
# Token for your bot
BOT_TOKEN=123456:ABC
# Add tokens or token for ai
CEREBRAS_TOKENS='csk-****, csk-****'
# Add admin id or ids for future
OWNER_IDS='123456'
```

## 4. Build and run with docker

```bash
docker compose up -d --build
```

[stand-with-ukraine]: https://img.shields.io/badge/Stand_With-Ukraine-yellow?style=for-the-badge&labelColor=blue
[stand-with-ukraine-url]: https://vshymanskyy.github.io/StandWithUkraine