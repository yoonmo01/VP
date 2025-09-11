# # app/services/langsmith.py

# import os
# from langsmith import Client

# # .env에서 읽는 방식이 편하면 아래처럼 사용 (dotenv 패키지 써도 됨)
# LANGSMITH_API_KEY = os.environ["LANGSMITH_API_KEY"]
# if not LANGSMITH_API_KEY:
#     raise RuntimeError(
#         "LANGSMITH_API_KEY 환경변수가 설정되어 있지 않습니다! Replit Secrets를 확인하세요.")

# # LangSmith 클라이언트 인스턴스화
# client = Client(api_key=LANGSMITH_API_KEY)

# # 트레이스 기록 함수 예시
# def trace_llm_run(inputs, outputs, metadata=None):
#     """LangSmith로 트레이스 로그 저장"""
#     run = client.create_run(inputs=inputs,
#                             outputs=outputs,
#                             metadata=metadata or {})
#     return run.id

# # LangChain LLM/Chain 실행 시점에 위 함수 활용 가능
