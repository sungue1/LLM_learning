# Docker 명령어 정리

> 기준: Docker Desktop (Docker Engine 27+ / Compose v2) / Windows PowerShell
> 전체 도움말: `docker --help`, 명령별 도움말: `docker <명령> --help`

---

## 1. 기본 확인

| 명령어 | 설명 |
|---|---|
| `docker version` | 클라이언트/서버(엔진) 버전 확인 |
| `docker info` | 엔진 상태, 컨테이너·이미지 개수 등 전체 정보 |
| `docker run hello-world` | 설치가 정상인지 테스트 |
| `docker login` | Docker Hub 로그인 |
| `docker logout` | 로그아웃 |

> `error during connect ...` 에러가 나면 Docker Desktop이 실행 중인지 먼저 확인하세요.

---

## 2. 이미지 (Image)

| 명령어 | 설명 |
|---|---|
| `docker pull 이미지명` | 이미지 다운로드 (태그 생략 시 `latest`) |
| `docker pull 이미지명:태그` | 특정 버전 다운로드 (예: `python:3.12-slim`) |
| `docker images` / `docker image ls` | 로컬 이미지 목록 |
| `docker rmi 이미지명` | 이미지 삭제 |
| `docker rmi -f 이미지ID` | 강제 삭제 (사용 중인 컨테이너가 있어도) |
| `docker image prune` | 이름 없는(dangling) 이미지 정리 |
| `docker image prune -a` | 사용하지 않는 모든 이미지 정리 |
| `docker tag 원본 새이름:태그` | 이미지에 새 이름/태그 붙이기 |
| `docker push 사용자명/이미지:태그` | Docker Hub에 업로드 |
| `docker history 이미지명` | 이미지 레이어 구성 확인 |
| `docker image inspect 이미지명` | 이미지 상세 정보 (JSON) |
| `docker search 키워드` | Docker Hub에서 이미지 검색 |

---

## 3. 컨테이너 실행 (`docker run`)

```powershell
docker run [옵션] 이미지명 [명령어]
```

| 옵션 | 설명 |
|---|---|
| `-d` | 백그라운드(detached) 실행 |
| `-it` | 대화형 터미널로 실행 (예: `bash`, `python` 접속) |
| `--name 이름` | 컨테이너 이름 지정 |
| `-p 호스트포트:컨테이너포트` | 포트 연결 (예: `-p 8080:80`) |
| `-v 호스트경로:컨테이너경로` | 폴더(볼륨) 연결 |
| `-e 키=값` | 환경 변수 설정 |
| `--env-file .env` | `.env` 파일의 환경 변수 전부 전달 |
| `--rm` | 종료 시 컨테이너 자동 삭제 |
| `--restart unless-stopped` | 재부팅/종료 시 자동 재시작 |
| `--network 네트워크명` | 특정 네트워크에 연결 |
| `-w 경로` | 컨테이너 안의 작업 디렉터리 지정 |
| `--gpus all` | GPU 사용 (NVIDIA, WSL2 환경) |

예시:

```powershell
# 파이썬 대화형 셸 (종료 시 삭제)
docker run -it --rm python:3.12-slim python

# Nginx 웹 서버를 8080 포트로
docker run -d --name web -p 8080:80 nginx

# 현재 폴더를 컨테이너 /app에 연결해 실행 (PowerShell)
docker run -it --rm -v ${PWD}:/app -w /app python:3.12-slim bash

# Ollama 서버 (GPU 사용)
docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

> PowerShell에서 현재 경로는 `${PWD}`, CMD에서는 `%cd%`, Git Bash에서는 `$(pwd)` 를 씁니다.

---

## 4. 컨테이너 관리

| 명령어 | 설명 |
|---|---|
| `docker ps` | 실행 중인 컨테이너 목록 |
| `docker ps -a` | 정지된 것 포함 전체 목록 |
| `docker stop 이름` | 컨테이너 정지 |
| `docker start 이름` | 정지된 컨테이너 다시 시작 |
| `docker restart 이름` | 재시작 |
| `docker rm 이름` | 컨테이너 삭제 (정지 상태여야 함) |
| `docker rm -f 이름` | 실행 중이어도 강제 삭제 |
| `docker container prune` | 정지된 컨테이너 모두 삭제 |
| `docker rename 기존 새이름` | 이름 변경 |
| `docker pause 이름` / `docker unpause 이름` | 일시 정지 / 재개 |

---

## 5. 컨테이너 내부 확인 / 접속

| 명령어 | 설명 |
|---|---|
| `docker logs 이름` | 로그 보기 |
| `docker logs -f 이름` | 로그 실시간 보기 (Ctrl+C로 종료) |
| `docker logs --tail 100 이름` | 마지막 100줄만 |
| `docker exec -it 이름 bash` | 실행 중인 컨테이너에 접속 (`bash` 없으면 `sh`) |
| `docker exec 이름 명령어` | 컨테이너 안에서 명령 1회 실행 |
| `docker attach 이름` | 메인 프로세스에 연결 (나올 때 `Ctrl+P, Ctrl+Q`) |
| `docker inspect 이름` | 상세 정보 (IP, 마운트, 환경 변수 등) |
| `docker stats` | CPU/메모리 사용량 실시간 확인 |
| `docker top 이름` | 컨테이너 안의 프로세스 목록 |
| `docker port 이름` | 포트 연결 정보 |
| `docker diff 이름` | 이미지 대비 변경된 파일 목록 |

---

## 6. 파일 복사

| 명령어 | 설명 |
|---|---|
| `docker cp 파일 이름:/경로` | 호스트 → 컨테이너 |
| `docker cp 이름:/경로/파일 .` | 컨테이너 → 호스트 (현재 폴더) |

---

## 7. 이미지 만들기 (Dockerfile / build)

| 명령어 | 설명 |
|---|---|
| `docker build -t 이름:태그 .` | 현재 폴더의 `Dockerfile`로 이미지 빌드 |
| `docker build -f 경로/Dockerfile -t 이름 .` | 다른 Dockerfile 지정 |
| `docker build --no-cache -t 이름 .` | 캐시 없이 처음부터 빌드 |
| `docker build --build-arg 키=값 -t 이름 .` | 빌드 인자(`ARG`) 전달 |
| `docker commit 컨테이너 새이미지명` | 현재 컨테이너 상태를 이미지로 저장 |
| `docker save -o 파일.tar 이미지명` | 이미지를 tar 파일로 저장 |
| `docker load -i 파일.tar` | tar 파일에서 이미지 불러오기 |

Dockerfile 예시 (uv 기반 파이썬 앱):

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
EXPOSE 8000
CMD ["uv", "run", "main.py"]
```

주요 Dockerfile 지시어:

| 지시어 | 설명 |
|---|---|
| `FROM` | 기반 이미지 |
| `WORKDIR` | 작업 디렉터리 |
| `COPY` / `ADD` | 파일 복사 (`ADD`는 URL·압축 해제 지원) |
| `RUN` | 빌드 중 명령 실행 |
| `ENV` | 환경 변수 |
| `ARG` | 빌드 시 인자 |
| `EXPOSE` | 사용할 포트 표시 (실제 연결은 `-p`) |
| `CMD` | 컨테이너 시작 시 기본 명령 (덮어쓰기 가능) |
| `ENTRYPOINT` | 고정 실행 명령 (`CMD`는 인자로 붙음) |

> `.dockerignore` 파일에 `.venv`, `__pycache__`, `.git`, `.env` 등을 넣어 빌드에서 제외하세요.

---

## 8. 볼륨 (Volume)

| 명령어 | 설명 |
|---|---|
| `docker volume create 이름` | 볼륨 생성 |
| `docker volume ls` | 볼륨 목록 |
| `docker volume inspect 이름` | 볼륨 상세 정보 |
| `docker volume rm 이름` | 볼륨 삭제 |
| `docker volume prune` | 사용하지 않는 볼륨 정리 |

> `-v 이름:/경로` → Docker가 관리하는 **볼륨**, `-v C:\폴더:/경로` → 호스트 폴더 **바인드 마운트**

---

## 9. 네트워크 (Network)

| 명령어 | 설명 |
|---|---|
| `docker network ls` | 네트워크 목록 |
| `docker network create 이름` | 네트워크 생성 |
| `docker network connect 네트워크 컨테이너` | 컨테이너를 네트워크에 연결 |
| `docker network disconnect 네트워크 컨테이너` | 연결 해제 |
| `docker network inspect 이름` | 상세 정보 (연결된 컨테이너 등) |
| `docker network rm 이름` | 네트워크 삭제 |

> 같은 사용자 정의 네트워크 안의 컨테이너끼리는 **컨테이너 이름**으로 접속할 수 있습니다.
> 컨테이너에서 호스트(Windows)의 서비스에 접속할 때는 `host.docker.internal` 을 사용합니다.
> (예: 호스트의 Ollama → `http://host.docker.internal:11434`)

---

## 10. Docker Compose

여러 컨테이너를 `compose.yaml`(또는 `docker-compose.yml`) 하나로 관리합니다.

| 명령어 | 설명 |
|---|---|
| `docker compose up` | 서비스 생성 + 실행 |
| `docker compose up -d` | 백그라운드 실행 |
| `docker compose up -d --build` | 이미지 다시 빌드 후 실행 |
| `docker compose down` | 컨테이너·네트워크 정지 및 삭제 |
| `docker compose down -v` | 볼륨까지 삭제 |
| `docker compose ps` | 서비스 상태 확인 |
| `docker compose logs -f` | 전체 로그 실시간 |
| `docker compose logs -f 서비스명` | 특정 서비스 로그 |
| `docker compose exec 서비스명 bash` | 서비스 컨테이너 접속 |
| `docker compose restart 서비스명` | 서비스 재시작 |
| `docker compose stop` / `start` | 정지 / 시작 (삭제는 안 함) |
| `docker compose build` | 이미지만 빌드 |
| `docker compose pull` | 이미지 최신으로 받기 |
| `docker compose config` | 최종 설정 확인 (문법 검사) |

`compose.yaml` 예시 (앱 + Ollama):

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama:/root/.ollama

volumes:
  ollama:
```

---

## 11. 정리 (디스크 확보)

| 명령어 | 설명 |
|---|---|
| `docker system df` | 이미지/컨테이너/볼륨이 쓰는 용량 |
| `docker system prune` | 정지 컨테이너·dangling 이미지·미사용 네트워크·빌드 캐시 삭제 |
| `docker system prune -a` | 사용하지 않는 이미지 전부 포함 삭제 |
| `docker system prune -a --volumes` | 볼륨까지 모두 삭제 (**주의: 데이터 손실**) |
| `docker builder prune` | 빌드 캐시만 삭제 |

---

## 12. 자주 쓰는 조합

```powershell
# 모든 컨테이너 정지 (PowerShell)
docker stop $(docker ps -q)

# 정지된 컨테이너 전부 삭제
docker container prune -f

# 특정 이름 컨테이너만 필터링
docker ps -a --filter "name=ollama"

# 보기 좋게 출력 형식 지정
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

# 컨테이너 IP 확인
docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" 이름
```

---

## 13. 자주 만나는 에러

| 증상 | 해결 |
|---|---|
| `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop 실행 확인 |
| `port is already allocated` | 해당 포트를 쓰는 컨테이너/프로그램 종료 또는 다른 포트 사용 (`-p 8081:80`) |
| `Conflict. The container name "/xxx" is already in use` | `docker rm -f xxx` 후 다시 실행 |
| `exec: "bash": executable file not found` | `bash` 대신 `sh` 사용 (alpine 등 경량 이미지) |
| 컨테이너가 바로 종료됨 | `docker logs 이름`으로 원인 확인, 실행할 메인 프로세스가 있는지 확인 |
| 컨테이너에서 `localhost`로 호스트 접속 불가 | `host.docker.internal` 사용 |
| 볼륨 마운트 경로가 비어 있음 | Docker Desktop → Settings → Resources → File sharing / WSL 통합 확인 |
