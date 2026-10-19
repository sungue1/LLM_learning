# CVE 점검 보고서

## 확인 대상
- Apache Log4j / 2.14.1
- Cisco AnyConnect / 4.9.0

## 조회 및 판정
### 1) Apache Log4j 2.14.1
- 조회 CVE: CVE-2021-44228
- 조회 결과: 영향 버전 `2.0-beta9 ~ 2.14.1`, 고정 버전 `2.17.1`
- 판정: **영향 받음**

### 2) Cisco AnyConnect 4.9.0
- 조회 CVE: 확인된 등록 CVE 없음
- 판정: **현재 조회한 CVE 기준 영향 확인 불가**

## 무엇을 어떻게 확인했는지
1. `input/assets.md`에서 사내 사용 제품과 버전을 읽음.
2. 제품별로 관련 CVE를 `cve-lookup` 도구로 조회함.
3. 조회 결과의 영향 버전 범위와 사내 사용 버전을 비교해 판정함.
4. 결과를 `output/report.md`에 저장함.
