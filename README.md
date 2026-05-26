# 2026학년도 1학기 인공지능 과제: 육목(Connect6) AI 학생용 배포 패키지

## 1. 과제 개요
이 과제의 목표는 육목(Connect6)을 플레이하는 AI를 직접 구현하고, 로컬 대국과 웹 플랫폼 대국 결과를 바탕으로 전략을 개선하는 것입니다.

학생은 `src/agent_template.py`의 `act(state, num_stones=2)` 함수를 완성합니다. 완성한 파일을 웹 플랫폼의 **과제 제출** 페이지에 업로드하고, 구현 전략과 실험 결과는 `01. report_template.docx`에 작성합니다.

## 2. 배포본 구성
- `00. instruction.html`: 과제 상세 안내문. 웹 사용법, 로컬 실행법, 제출 규칙을 포함합니다.
- `01. report_template.docx`: 보고서 작성 양식.
- `src/agent_template.py`: 학생이 수정하고 최종 제출할 AI 파일.
- `src/main.py`: 로컬 대국/검증/벤치마크를 실행하는 통합 진입점.
- `src/connect6/`: 게임 상태 엔진 모듈.
- `src/tools/`: 로컬 실행 도구 구현 모듈.
- `src/reference_agents/`: 로컬 동작 확인용 기준 에이전트 모듈. 완성 전략 AI가 아닙니다.
- `assets/`: 웹 사용 안내에 들어가는 화면 예시 이미지.

배포본에는 완성된 전략 AI 또는 정답 코드가 포함되어 있지 않습니다.

## 3. 로컬에서 해야 할 일
작업은 `src/` 폴더에서 진행합니다.

```bash
cd src
uv sync
```

직접 AI와 대국하며 수를 확인합니다.

```bash
uv run python main.py play agent_template.py
uv run python main.py play agent_template.py --human white
```

제출 전 형식 검증을 실행합니다.

```bash
uv run python main.py check agent_template.py
uv run python main.py benchmark agent_template.py --validate-only
```

랜덤 기준 AI와 자동 대국을 실행합니다.

```bash
uv run python main.py benchmark agent_template.py
uv run python main.py benchmark agent_template.py --show-final-board
uv run python main.py benchmark agent_template.py --save-log local_result.json --seed 42
```

`uv`를 사용할 수 없는 경우:

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py play agent_template.py
python main.py check agent_template.py
```

## 4. AI 구현 규약
반드시 다음 함수를 구현해야 합니다.

```python
def act(state, num_stones=2):
    return [(7, 7)] if num_stones == 1 else [(7, 7), (7, 8)]
```

- 반환형은 항상 `list[(row, col)]`입니다.
- 첫 흑 턴에는 `num_stones=1`이므로 좌표 1개를 반환합니다.
- 이후 턴에는 일반적으로 `num_stones=2`이므로 좌표 2개를 반환합니다.
- 좌표는 0부터 시작합니다. 예: 중앙 근처는 `(7, 7)`입니다.
- 이미 돌이 있는 좌표, 보드 밖 좌표, 한 턴 안의 중복 좌표는 허용되지 않습니다.
- 코드가 예외를 내거나 제한 시간 안에 반환하지 못하면 대국에서 패배 처리될 수 있습니다.

## 5. 웹 플랫폼 사용 흐름
로그인 후 왼쪽 메뉴에서 다음 페이지를 사용합니다.

1. **메인홈**: 템플릿 다운로드, 규칙 실습, 연습 대국, 공식 제출로 이동합니다.
2. **규칙 실습**: 브라우저에서 직접 육목을 두며 규칙과 턴 구조를 익힙니다. 흑은 첫 턴 1수, 이후 양쪽 모두 2수씩 둡니다.
3. **연습 대국**: `agent_template.py`를 업로드하거나 코드를 붙여넣어 서버에서 기준 AI와 연습 대국을 실행합니다. 공식 점수에는 반영되지 않습니다.
4. **과제 제출**: 최종 `agent_template.py`를 공식 제출합니다. 제출된 코드는 활성 버전으로 등록되고 이후 공식 재평가 라운드에 반영됩니다.
5. **리더보드**: 같은 분반 학생들의 공식 재평가 결과를 Elo 순위로 확인합니다. 분반별로 별도 운영됩니다.

리더보드에서 본인 항목을 선택하면 **내 제출 상세**에서 현재 Elo, 승률, 최근 공식 대국, Elo 변화량, 종료 사유를 확인할 수 있습니다. 공식 제출 페이지의 **결과 보기** 탭에서도 제출 이력과 최근 공식 대국 보드를 확인할 수 있습니다.

## 6. 리더보드와 점수 해석
- 리더보드는 공식 제출된 활성 코드만 반영합니다.
- 연습 대국 결과는 리더보드 점수에 직접 반영되지 않습니다.
- Elo는 상대와의 공식 대국 결과에 따라 변합니다.
- 서버 재평가 시점에 따라 제출 직후 순위가 바로 바뀌지 않을 수 있습니다.
- 승리뿐 아니라 시간 초과, 예외, 잘못된 반환 형식, 불법 착수도 결과에 영향을 줍니다.

## 7. 보고서에 작성할 내용
`01. report_template.docx`에 다음 내용을 작성합니다.

- 구현한 AI의 핵심 아이디어
- 사용한 AI 기법: rule-based, heuristic evaluation, minimax, alpha-beta pruning, beam search 등
- 후보 수를 고르는 방법
- 공격/수비 판단 기준
- 평가 함수 또는 탐색 알고리즘
- 시간 제한을 넘기지 않기 위한 후보 제한/가지치기/예외 처리
- 로컬 직접 대국에서 관찰한 장점과 약점
- 로컬 자동 대국 결과
- 웹 연습 대국 결과
- 공식 제출 후 리더보드/상세 페이지에서 확인한 결과
- 실패 사례와 개선 방향
- 생성형 AI를 사용했다면 사용 범위와 본인 검증 내용

## 8. 제출물
- 웹 공식 제출: `src/agent_template.py`
- 보고서 제출: 작성 완료한 `01. report_template.docx` 또는 수업에서 지정한 변환 파일

파일명, 함수명, 반환 규약을 임의로 바꾸지 마십시오.

## 9. 코드 폴더 구조
학생이 주로 수정할 파일은 `src/agent_template.py` 하나입니다. 나머지 폴더는 로컬 실행을 돕기 위한 보조 코드입니다.

```text
src/
  agent_template.py          # 수정/제출 대상
  main.py                    # 로컬 도구 통합 실행 파일
  connect6/
    yukmok.py                # 게임 상태 엔진
  tools/
    play_local.py            # 직접 대국 구현
    local_test_runner.py     # 검증/자동 대국 구현
    check_submission.py      # 빠른 검증 구현
  reference_agents/
    random_agent.py          # 로컬 확인용 랜덤 AI
```

공식 제출에는 `agent_template.py`만 업로드합니다. `connect6`, `tools`, `reference_agents`를 import하는 방식으로 제출 코드를 작성하면 서버 제출 환경에서 동작하지 않을 수 있으므로 주의하십시오.

## 10. AI 구현 방향
- 가장 먼저 합법수 반환과 시간 내 반환을 안정화합니다.
- 그 다음 중앙 선호, 기존 돌 주변 후보 생성, 즉시 승리/방어 탐지 같은 휴리스틱을 추가합니다.
- 더 발전시키고 싶다면 후보 상위 N개에 대해 minimax, alpha-beta pruning, beam search를 제한적으로 적용합니다.
- `agent_template.py`에는 `generate_candidates`, `evaluate_move`, `choose_one_move` 뼈대가 들어 있습니다. 이 함수들을 중심으로 후보 수 생성, 상태 평가 함수, 최종 의사결정을 나누어 구현하면 보고서 작성도 쉬워집니다.
- 생성형 AI를 활용했다면 보고서에 어떤 부분에서 도움을 받았고 어떻게 검증했는지 작성합니다.
