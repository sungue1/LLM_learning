# git 명령어 정리

> 기준: Git 2.55 (Git for Windows) / Windows PowerShell
> 전체 도움말: `git help`, 명령별 도움말: `git <명령> --help`

---

## 1. 처음 설정 (PC당 한 번)

| 명령어 | 설명 |
|---|---|
| `git config --global user.name "이름"` | 커밋 작성자 이름 설정 |
| `git config --global user.email "메일"` | 커밋 작성자 이메일 설정 (GitHub 계정 이메일과 같아야 프로필에 연결됨) |
| `git config --global init.defaultBranch main` | 새 저장소의 기본 브랜치를 `main`으로 |
| `git config --global core.autocrlf true` | 줄바꿈 자동 변환 (Windows 권장, Git for Windows 기본값) |
| `git config --list --show-origin` | 모든 설정과 그 설정이 들어 있는 파일 보기 |
| `git config --get user.email` | 특정 설정값 하나만 보기 |

> 설정 범위: `--system`(PC 전체) < `--global`(내 계정, `~/.gitconfig`) < `--local`(이 저장소, `.git/config`)
> 같은 항목이 여러 곳에 있으면 오른쪽(더 좁은 범위)이 우선합니다.

---

## 2. 저장소 만들기 / 가져오기

| 명령어 | 설명 |
|---|---|
| `git init` | 현재 폴더를 git 저장소로 초기화 (`.git/` 생성) |
| `git clone URL` | 원격 저장소를 새 폴더로 복제 |
| `git clone URL 폴더명` | 원하는 폴더 이름으로 복제 |
| `git rev-parse --show-toplevel` | 현재 위치가 속한 저장소의 최상위 폴더 확인 |

> `fatal: not a git repository` 에러 → 현재 폴더(와 상위 폴더)에 `.git`이 없다는 뜻입니다.
> → `git init`을 하거나, 저장소 폴더로 이동하세요.

---

## 3. 기본 작업 흐름 (수정 → 스테이징 → 커밋)

| 명령어 | 설명 |
|---|---|
| `git status` | 변경된 파일 / 스테이징 상태 확인 |
| `git status -s` | 짧은 형식으로 보기 |
| `git add 파일명` | 파일을 스테이징 (커밋할 목록에 올림) |
| `git add .` | 현재 폴더 아래 모든 변경사항 스테이징 |
| `git add -p` | 변경 내용을 조각별로 골라서 스테이징 |
| `git commit -m "메시지"` | 스테이징된 내용으로 커밋 |
| `git commit -am "메시지"` | 추적 중인 파일의 변경을 add + commit 한 번에 (새 파일은 제외) |
| `git commit --amend` | 마지막 커밋 메시지/내용 수정 (push 전에만 사용) |

```powershell
git status
git add .
git commit -m "작업 내용 요약"
```

---

## 4. 변경 내용 / 기록 보기

| 명령어 | 설명 |
|---|---|
| `git diff` | 아직 스테이징 안 한 변경 내용 |
| `git diff --staged` | 스테이징된(커밋 예정) 변경 내용 |
| `git log` | 커밋 기록 |
| `git log --oneline` | 한 줄씩 간단히 |
| `git log --oneline --graph --all` | 브랜치 그래프와 함께 보기 |
| `git log -p 파일명` | 특정 파일의 변경 이력 |
| `git show 커밋ID` | 특정 커밋의 내용 |
| `git show --stat HEAD` | 마지막 커밋에서 바뀐 파일 목록 |
| `git ls-files` | git이 추적 중인 파일 목록 |

> `log`가 길어서 화면이 멈춘 것처럼 보이면 `q`를 눌러 빠져나옵니다.

---

## 5. 원격 저장소 (GitHub)

| 명령어 | 설명 |
|---|---|
| `git remote -v` | 연결된 원격 저장소 확인 (비어 있으면 연결 안 됨) |
| `git config --get remote.origin.url` | origin 주소만 확인 |
| `git remote add origin URL` | 원격 저장소를 `origin`이라는 이름으로 연결 |
| `git remote set-url origin URL` | origin 주소 변경 |
| `git remote remove origin` | 연결 해제 |
| `git ls-remote origin` | 원격 접속/인증이 되는지 확인 |
| `git push -u origin main` | 처음 push (이후 `git push`만 해도 되도록 연결) |
| `git push` | 내 커밋을 원격에 올리기 |
| `git pull` | 원격의 변경을 받아와서 합치기 (`fetch` + `merge`) |
| `git fetch` | 원격의 변경을 받아오기만 함 (합치지 않음) |

**로컬 폴더를 GitHub에 처음 올리기**

1. GitHub에서 **빈 저장소** 생성 (README / .gitignore / license 추가 X)
2. 아래 명령 실행

```powershell
git remote add origin https://github.com/사용자명/저장소명.git
git branch -M main
git push -u origin main
```

> 처음 push할 때 GitHub 로그인 창이 뜹니다. (Git Credential Manager가 로그인 정보를 저장)
> `rejected ... fetch first` 에러 → 원격에 내 PC에 없는 커밋이 있다는 뜻 → `git pull` 후 다시 push

---

## 6. 브랜치

| 명령어 | 설명 |
|---|---|
| `git branch` | 로컬 브랜치 목록 (`*`가 현재 브랜치) |
| `git branch -a` | 원격 브랜치까지 모두 보기 |
| `git switch 브랜치명` | 브랜치 이동 |
| `git switch -c 브랜치명` | 새 브랜치를 만들고 이동 |
| `git branch -M main` | 현재 브랜치 이름을 `main`으로 변경 |
| `git merge 브랜치명` | 현재 브랜치에 다른 브랜치를 합치기 |
| `git branch -d 브랜치명` | 브랜치 삭제 (합쳐진 경우만) |
| `git push origin --delete 브랜치명` | 원격 브랜치 삭제 |

> 예전 명령인 `git checkout 브랜치명`, `git checkout -b 브랜치명`도 같은 동작입니다.

---

## 7. 되돌리기

| 명령어 | 설명 |
|---|---|
| `git restore 파일명` | 수정한 파일을 마지막 커밋 상태로 되돌림 (**수정 내용 사라짐**) |
| `git restore --staged 파일명` | 스테이징 취소 (수정 내용은 유지) |
| `git rm --cached 파일명` | git 추적만 중단 (PC의 파일은 유지) |
| `git rm -r --cached 폴더명` | 폴더 추적 중단 (예: 실수로 올린 `__pycache__`) |
| `git reset --soft HEAD~1` | 마지막 커밋 취소, 변경 내용은 스테이징 상태로 유지 |
| `git reset HEAD~1` | 마지막 커밋 취소, 변경 내용은 파일에 유지 |
| `git reset --hard HEAD~1` | 마지막 커밋과 변경 내용까지 모두 삭제 (**복구 어려움**) |
| `git revert 커밋ID` | 해당 커밋을 취소하는 새 커밋 생성 (이미 push한 경우 이것을 사용) |

> 이미 push한 커밋은 `reset` 대신 `revert`를 쓰세요.
> (`reset` 후 push하려면 강제 push가 필요하고, 다른 사람 작업과 충돌합니다)

---

## 8. 임시 저장 (stash)

| 명령어 | 설명 |
|---|---|
| `git stash` | 커밋하지 않은 변경을 잠시 치워둠 |
| `git stash -u` | 새 파일(untracked)까지 포함해서 치워둠 |
| `git stash list` | 치워둔 목록 |
| `git stash pop` | 가장 최근 것을 다시 꺼내고 목록에서 삭제 |
| `git stash drop` | 가장 최근 것을 버림 |

---

## 9. .gitignore

git이 무시할 파일/폴더를 적는 파일입니다. 저장소 최상위에 `.gitignore`로 만듭니다.

```gitignore
# Python
__pycache__/
*.py[cod]

# Virtual environment
.venv/

# Environment variables (API 키 등)
.env
```

| 명령어 | 설명 |
|---|---|
| `git check-ignore -v 파일명` | 그 파일이 왜 무시되는지 (어느 규칙인지) 확인 |
| `git status --ignored` | 무시된 파일까지 보기 |

> `.gitignore`는 **아직 추적하지 않은 파일**에만 적용됩니다.
> 이미 커밋된 파일은 `git rm --cached`로 추적을 끊은 뒤 커밋해야 합니다.
> `.env`에 들어 있는 API 키는 절대 커밋하지 마세요. (한 번 push되면 키를 재발급해야 합니다)

---

## 자주 쓰는 흐름

**매일 작업 후 올리기**

```powershell
git status
git add .
git commit -m "작업 내용"
git push
```

**다른 PC에서 이어서 작업하기**

```powershell
git clone https://github.com/사용자명/저장소명.git   # 처음 한 번
git pull                                             # 이후에는 작업 전에 pull
uv sync                                              # 파이썬 환경 복원
```

**GitHub 연결 상태 확인**

```powershell
git remote -v          # origin 주소가 보이면 연결 설정 완료
git ls-remote origin   # 에러 없이 끝나면 인증까지 정상
git status -sb         # [ahead 1] = 아직 push 안 한 커밋 1개
```

---

## 주요 파일 / 용어

| 이름 | 의미 |
|---|---|
| `.git/` | 저장소 데이터 전체 (지우면 기록이 모두 사라짐) |
| `.git/config` | 이 저장소 설정 (원격 주소 등) |
| `~/.gitconfig` | 내 계정 전체 설정 (이름, 이메일) |
| `.gitignore` | git이 무시할 파일 목록 |
| `origin` | 원격 저장소의 기본 이름 |
| `HEAD` | 현재 보고 있는 커밋 (`HEAD~1` = 그 이전 커밋) |
| 스테이징(index) | 다음 커밋에 들어갈 변경 목록 (`git add`로 올림) |
