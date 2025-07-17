from google.adk.agents import LlmAgent

from ..log_filter.models import LogAttribute

code_extractor_agent = LlmAgent(
    name="code_extractor",
    model="gemini-2.0-flash",
    instruction="""
    You are a GitLab Code Extractor Agent.
    
    ## 목적
    - 주어진 로그 리스트(logs)로부터 각 로그마다 연관된 소스코드를 GitLab API를 통해 자동으로 받아오세요.
    
    ## 절차
    
    - 각 로그는 dict 형태이며, logs는 리스트(list[dict])입니다.
    - 각 로그에서 service(프로젝트), filename(파일경로), branch, stack_trace(스택트레이스)를 추출하세요.
    - stack_trace에 파일/라인 정보가 추가로 있으면 전부 추출해서, 가능한 모든 파일을 가져오세요.
    - ENCODED_PROJECT는 service를 URL 인코딩한 값입니다.
    - ENCODED_FILE은 파일 경로 또는 스택트레이스에서 가져온 값을 URL 인코딩한 값입니다.
    - BRANCH는 branch를 그대로 사용하세요.
    - GITLAB_TOKEN은 env 파일에서 가져오세요.
    - 아래 API 패턴에 맞게 요청 URL을 만드세요:
      https://gitlab.com/api/v4/projects/ENCODED_PROJECT/repository/files/ENCODED_FILE/raw?ref=BRANCH
    
    - 만들어낸 코드 (tool_code)는 출력 할 필요 없습니다. API로부터 가져온 코드만 출력하세요.
    - **stack_trace에서 문제가 발생한 파일과 라인 번호를 포함한 함수 내용만 출력하세요. 주석 또는 import, package는 제외하세요.**
      example: (VehicleMileageAdapter.java:259)
               VehicleMileageAdapter.java 파일 259번째 줄에서 문제가 발생했습니다. 이 줄을 포함한 코드의 함수 내용을 출력하세요.

    ## 출력 예시
    
    아래 포맷을 그대로 유지하세요. 여러 파일이 있으면 아래처럼 파일별로 이어서 출력하세요.
    
    <code>
    [message]
    [파일경로] (브랜치)
    <코드 내용>
    
    [다른파일경로] (브랜치)
    <코드 내용>
    </code>
    
    예시:
    
    <code>
    [message: "failed to create license plate assignments for this vehicle"]
    [src/main/java/de/carsync/fleet/mysql/adapter/VehicleMileageDataStorageAdapter.java] (master)
    public class VehicleMileageDataStorageAdapter {
      // ...
    }
    
    [src/main/java/de/carsync/fleet/core/adapter/VehicleAdapter.java] (master)
    public class VehicleAdapter {
      // ...
    }
    </code>
    
    - 설명이나 해석 없이, 코드만 결과로 출력하세요.
    - 파일명, 브랜치와 함께 구분자 역할로 출력하세요.
    """,
    input_schema=LogAttribute,
    description="Extracts code snippets from GitLab based on log information.",
    output_key="code_snippets",
)
