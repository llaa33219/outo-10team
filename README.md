# outo-10team

10개의 AI 에이전트 팀을 격리된 Podman 컨테이너에서 오케스트레이션하는 PyPI 패키지

## 설치

```bash
pip install outo-10team
```

## 설정

```bash
outo-10team setup
```

## 실행

```bash
outo-10team run
```

## 명령어

- `outo-10team setup` - 초기 설정 (LLM, chatserver, 봇 비밀번호)
- `outo-10team run` - 모든 팀 컨테이너 시작
- `outo-10team status` - 컨테이너 상태 확인
- `outo-10team logs TEAM` - 팀 로그 확인
- `outo-10team stop` - 모든 컨테이너 중지
- `outo-10team build` - Podman 이미지 빌드

## 아키텍처

```
Host Machine
├── ~/.outo-10team/config.json
├── ~/.outo-10team/data/{teamname}/
└── Podman (10 containers)
    ├── archlinux container
    ├── uv → outo-agentcore
    └── watcher.py (polls chatserver REST API)
```

## 10개 팀

| 팀 | 역할 |
|---|---|
| main | 리더/코디네이터 |
| research | 연구/조사 |
| dev | 개발 |
| design | 디자인 |
| data | 데이터 분석 |
| security | 보안 |
| infra | 인프라/DevOps |
| qa | 품질보증 |
| docs | 문서화 |
| support | 지원/고객서비스 |
