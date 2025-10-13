from langchain_core.callbacks.base import BaseCallbackHandler
from app.core.logging import get_logger

logger = get_logger(__name__)


class RoundLimitReached(Exception):
    """라운드 제한 도달 예외"""
    pass


class RoundLimitStoppingCallback(BaseCallbackHandler):
    """
    라운드 제한을 강제하는 콜백
    - max_rounds 도달 시 더 이상 도구 호출 차단
    - admin.make_prevention 호출 후 종료
    """
    
    def __init__(self, max_rounds: int = 5):
        super().__init__()
        self.max_rounds = max_rounds
        self.current_rounds = 0
        self.make_prevention_called = False
        self.session_terminated = False
        
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        """도구 실행 전에 호출됨"""
        tool_name = serialized.get("name", "")
        
        # 세션이 종료되었으면 모든 도구 차단
        if self.session_terminated:
            logger.warning(f"[StoppingCallback] 세션 종료됨 - {tool_name} 호출 차단")
            raise RoundLimitReached("이 세션은 이미 종료되었습니다.")
        
        # admin.make_prevention 호출 감지
        if tool_name == "admin.make_prevention":
            logger.info("[StoppingCallback] admin.make_prevention 호출 감지")
            self.make_prevention_called = True
            return
        
        # admin.make_prevention 호출 후에는 다른 도구 차단
        if self.make_prevention_called:
            logger.warning(f"[StoppingCallback] admin.make_prevention 호출 후 - {tool_name} 차단")
            raise RoundLimitReached("admin.make_prevention 호출 후 종료")
        
        # mcp.simulator_run 호출 시 라운드 카운트
        if tool_name == "mcp.simulator_run":
            self.current_rounds += 1
            logger.info(f"[StoppingCallback] 라운드 {self.current_rounds}/{self.max_rounds}")
            
            if self.current_rounds > self.max_rounds:
                logger.warning(f"[StoppingCallback] 최대 라운드 초과: {self.current_rounds}")
                raise RoundLimitReached(f"최대 {self.max_rounds}라운드 초과")
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """도구 실행 후 호출됨"""
        # admin.make_prevention 완료 시 세션 종료
        if self.make_prevention_called and not self.session_terminated:
            logger.info("[StoppingCallback] admin.make_prevention 완료 - 세션 종료")
            self.session_terminated = True
    
    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:
        """체인 시작 시 호출됨 - 종료된 세션에서는 차단"""
        if self.session_terminated:
            logger.warning("[StoppingCallback] 세션 종료됨 - 새 체인 시작 차단")
            raise RoundLimitReached("이 세션은 이미 종료되었습니다.")
    
    def on_agent_action(self, action, **kwargs) -> None:
        """에이전트 액션 시 호출됨 - 종료된 세션에서는 차단"""
        if self.session_terminated:
            tool_name = getattr(action, "tool", "unknown")
            logger.warning(f"[StoppingCallback] 세션 종료됨 - {tool_name} 액션 차단")
            raise RoundLimitReached("이 세션은 이미 종료되었습니다.")